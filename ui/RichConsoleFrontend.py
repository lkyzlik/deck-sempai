import sys
import time
from typing import Optional

from rich.console import Console, Group
from rich.live import Live
from rich.table import Table
from rich import box
from rich.measure import Measurement
from rich.text import Text
from rich.progress import MofNCompleteColumn, Progress, ProgressColumn, TextColumn

from Deck import Deck, DeckMeta, Field
from DeckOperator import DeckOpResult, DeckOpError

from ui.Logger import LoggerProgress

try:
    import termios
    import tty
except ImportError:
    termios = None
    tty = None

try:
    import msvcrt
except ImportError:
    msvcrt = None


class _StyledMofNCompleteColumn(MofNCompleteColumn):
    def __init__(self, style: str, **kwargs):
        self.style = style
        super().__init__(**kwargs)

    def render(self, task) -> Text:
        if task.total == 1:
            return Text("")
        text = super().render(task)
        text.style = self.style
        return text


class _FlowerBar:
    # A bud opening into full bloom, stage by stage.
    STAGES = ["·", "⋆", "✦", "✳", "❀"]

    def __init__(self, total: Optional[float], completed: float, style: str, bud_style: str,
                 stage_char: Optional[str], width: Optional[int] = None):
        self.total = total
        self.completed = completed
        self.style = style
        self.bud_style = bud_style
        self.stage_char = stage_char
        self.width = width

    def __rich_console__(self, console, options):
        width = min(self.width, options.max_width) if self.width is not None else options.max_width

        bloomed_count = int(width * self.completed / self.total) if self.total else 0
        remaining = width - bloomed_count

        text = Text()
        if bloomed_count:
            text.append(self.STAGES[-1] * bloomed_count, style=self.style)
        if remaining and self.stage_char is not None:
            text.append(self.stage_char, style=self.style)
            remaining -= 1
        if remaining:
            text.append(self.STAGES[0] * remaining, style=self.bud_style)
        yield text

    def __rich_measure__(self, console, options):
        if self.width is None:
            return Measurement(4, options.max_width)
        # One flower per step, capped to whatever actually fits on the line.
        max_width = min(self.width, options.max_width)
        return Measurement(min(1, max_width), max_width)


class _FlowerBarColumn(ProgressColumn):
    STAGES_PER_SECOND = 4

    def __init__(self, style: str, width: Optional[int] = None, **kwargs):
        self.width = width
        self.style = style
        self.bud_style = "dim " + style
        super().__init__(**kwargs)

    def render(self, task) -> _FlowerBar:
        stage_char = None
        if task.total and not task.finished:
            stage = int(time.monotonic() * self.STAGES_PER_SECOND) % len(_FlowerBar.STAGES)
            stage_char = _FlowerBar.STAGES[stage]

        # One flower per step by default, unless an explicit width was set.
        width = self.width if self.width is not None else (int(task.total) if task.total else None)

        return _FlowerBar(
            total=task.total,
            completed=task.completed,
            style=self.style,
            bud_style=self.bud_style,
            stage_char=stage_char,
            width=width,
        )


class RichConsoleFrontend:
    COLOR_PRIMARY = "#fae9c8"
    COLOR_SECONDARY = "#a8813a"
    COLOR_ACCENT = "#a14d33"
    COLOR_INFO = "blue"
    COLOR_WARNING = "yellow"
    COLOR_ERROR = "red"

    def __init__(self, console: Console = Console()):
        self.console = console


    def _field_to_rich(self, field: Field):
        text = Text()
        text.append(field.get_text_oneline())
        for sound in field.sounds:
            text.append(Text(" [♪]", style=self.COLOR_ACCENT))
        return text


    def print(self, message: str):
        self.console.print(message, style=self.COLOR_PRIMARY)


    def info(self, message: str):
        text = Text()
        text.append("Info: ", style="bold " + self.COLOR_INFO)
        text.append(message, style=self.COLOR_INFO)
        self.console.print(text)


    def error(self, message: str):
        text = Text()
        text.append("Error: ", style="bold " + self.COLOR_ERROR)
        text.append(message, style=self.COLOR_ERROR)
        self.console.print(text)


    def warning(self, message: str):
        text = Text()
        text.append("Warning: ", style="bold " + self.COLOR_WARNING)
        text.append(message, style=self.COLOR_WARNING)
        self.console.print(text)


    def progress(self) -> LoggerProgress:
        return Progress(
            TextColumn("{task.description}", style=self.COLOR_PRIMARY),
            _FlowerBarColumn(style=self.COLOR_PRIMARY),
            _StyledMofNCompleteColumn(style=self.COLOR_PRIMARY),
            console=self.console
        )


    def show_deck(self, deck: Deck, result: DeckOpResult = None,
                  include_metadata: bool = True, max_rows: int = None):
        
        # Validate max_rows
        if max_rows and (max_rows > len(deck.notes) or max_rows < 0):
            self.warning(f"Can't show {max_rows} rows. Showing all notes instead.")
            max_rows = None

        if include_metadata:
            self.show_deck_name(deck.name)
            self.show_deck_metadata(deck.meta)

        notes = deck.notes[:max_rows] if max_rows else deck.notes
        show_index = len(notes) > 1

        table = Table(
            show_header=True,
            box=box.DOUBLE_EDGE,
            border_style=self.COLOR_SECONDARY,
            header_style=self.COLOR_PRIMARY + " bold",
            row_styles=[self.COLOR_PRIMARY, self.COLOR_SECONDARY],
        )
        if show_index:
            table.add_column("#")
        table.add_column("☖ Front")
        table.add_column("☗ Back")
        if result:
            table.add_column(result.op_title)

        for i, note in enumerate(notes):
            row = []
            if show_index:
                row.append(str(i + 1))
            row += [
                self._field_to_rich(note.front),
                self._field_to_rich(note.back),
            ]
            if result:
                note_result = result.note_results[i]
                status = "✓" if note_result.success else "✗"
                row.append(Text(status, style="green" if note_result.success else "red"))
            table.add_row(*row)

        self.console.print(table)


    def preview(self, prompt: str, deck: Deck, result: DeckOpResult = None) -> str:
        self.show_deck(deck, result, include_metadata=False)
        return self.input(prompt)


    def input(self, prompt: str) -> str:
        self.console.print(prompt, style="italic " + self.COLOR_PRIMARY, end="")
        return input()


    def input_multiline(self, prompt: str) -> list[str]:
        self.console.print(prompt, style="italic " + self.COLOR_PRIMARY)
        lines = []
        while True:
            line = self.input("> ").strip()
            if not line:
                break
            lines.append(line)
        return lines


    def _read_key(self) -> Optional[str]:
        """Reads a single keypress, returning "up"/"down"/"enter", a single printable
        character, or None for anything else (ignored). Raises KeyboardInterrupt on
        Ctrl+C, since raw mode otherwise swallows it instead of raising SIGINT."""
        if msvcrt:
            ch = msvcrt.getch()
            if ch == b"\x03":
                raise KeyboardInterrupt
            if ch in (b"\x00", b"\xe0"):
                return {b"H": "up", b"P": "down"}.get(msvcrt.getch())
            if ch in (b"\r", b"\n"):
                return "enter"
            try:
                decoded = ch.decode()
            except UnicodeDecodeError:
                return None
            return decoded if decoded.isprintable() else None

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == "\x03":
                raise KeyboardInterrupt
            if ch == "\x1b":
                if sys.stdin.read(1) != "[":
                    return None
                return {"A": "up", "B": "down"}.get(sys.stdin.read(1))
            if ch in ("\r", "\n"):
                return "enter"
            return ch if ch.isprintable() else None
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


    def _render_choice(self, options: list[str], selected: int) -> Group:
        lines = []
        for i, option in enumerate(options, 1):
            text = Text()
            if i - 1 == selected:
                text.append("❯ ", style=self.COLOR_ACCENT + " bold")
                text.append(f"{i}. ", style=self.COLOR_ACCENT + " bold")
                text.append(option, style=self.COLOR_ACCENT + " bold")
            else:
                text.append("  ")
                text.append(f"{i}. ", style=self.COLOR_SECONDARY + " bold")
                text.append(option, style=self.COLOR_SECONDARY)
            lines.append(text)

        return Group(*lines)


    def _choice_by_input(self, options: list[str]) -> str:
        for i, option in enumerate(options, 1):
            text = Text()
            text.append(f"{i}. ", style=self.COLOR_SECONDARY + " bold")
            text.append(option, style=self.COLOR_SECONDARY)
            self.console.print(text)

        while True:
            answer = self.input("> ").strip()
            if answer.isdigit() and 1 <= int(answer) <= len(options):
                return options[int(answer) - 1]
            self.error(f"Enter a number between 1 and {len(options)}.")


    def choice(self, prompt: str, options: list[str]) -> str:
        if prompt:
            self.console.print(prompt, style="italic " + self.COLOR_PRIMARY)

        can_read_keys = msvcrt or (termios and tty)
        if not sys.stdin.isatty() or not can_read_keys:
            return self._choice_by_input(options)

        selected = 0
        with Live(self._render_choice(options, selected), console=self.console, auto_refresh=False, transient=False) as live:
            while True:
                key = self._read_key()
                if key == "up":
                    selected = (selected - 1) % len(options)
                elif key == "down":
                    selected = (selected + 1) % len(options)
                elif key == "enter":
                    break
                elif key is not None and key.isdigit() and key != "0" and int(key) <= len(options):
                    selected = int(key) - 1
                    break
                else:
                    continue
                live.update(self._render_choice(options, selected))
                live.refresh()

        return options[selected]


    def show_deck_metadata(self, meta: DeckMeta):
        for key, value in meta.to_dict().items():
            text = Text()
            text.append(f"{key}: ", style=self.COLOR_SECONDARY + " bold")
            text.append(str(value), style=self.COLOR_SECONDARY)
            self.console.print(text)


    def show_deck_name(self, name: str):
        text = Text()
        text.append("Deck: ", style=self.COLOR_PRIMARY + " bold")
        text.append(name, style=self.COLOR_PRIMARY)
        self.console.print(text)
