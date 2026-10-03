import sys
import time
from contextlib import AbstractContextManager, contextmanager
from typing import Callable, Optional

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
from ui.frontend.Frontend import InteractiveAbort
from ui.frontend.TuiFrontend import TabSwitch

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
    COLOR_QUIET = "grey50"
    COLOR_INFO = "blue"
    COLOR_WARNING = "yellow"
    COLOR_ERROR = "red"

    def __init__(self, console: Console = Console()):
        self.console = console
        # Set for the duration of fullscreen()'s `with` block — choice()/choice_multi()/
        # input_multi()/deck() read this instead of taking a per-call flag, since the tabbed TUI
        # chrome (Tab/Shift+Tab switches tabs, the matching hint text) is only active in
        # fullscreen mode.
        self._fullscreen = False


    def _field_to_rich(self, field: Field):
        text = Text()
        text.append(field.get_text_oneline())
        for sound in field.sounds:
            text.append(Text(" [♪]", style=self.COLOR_ACCENT))
        return text


    def print(self, message: str):
        self.console.print(message, style=self.COLOR_PRIMARY)


    @property
    def is_fullscreen(self) -> bool:
        return self._fullscreen


    @contextmanager
    def fullscreen(self) -> AbstractContextManager:
        self._fullscreen = True
        try:
            with self.console.screen():
                yield
        finally:
            self._fullscreen = False


    def clear(self):
        self.console.clear()


    def hint(self, message: str):
        self.console.print()
        self.console.print(message, style="italic " + self.COLOR_QUIET)


    def status_bar(self, version: str, current_deck: Deck):
        text = Text()
        text.append("Deck Sempai", style=self.COLOR_PRIMARY + " bold")
        text.append(f" · v{version} · Current deck: ", style=self.COLOR_PRIMARY)
        text.append(current_deck.name, style=self.COLOR_PRIMARY + " bold")
        text.append(f" ({len(current_deck.notes)} cards)", style=self.COLOR_PRIMARY)
        self.console.print(text)
        self.console.print()


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


    def deck_notes(self, deck: Deck, result: DeckOpResult = None, top_row: int = None, height: int = None,
                   col_width: int = 40) -> Table:
        notes = deck.notes
        total = len(notes)

        # A caller passing top_row is windowing/scrolling through the deck (only the Show tab
        # does this) — in that case a boundary row is always drawn above and below the visible
        # notes (blank when nothing is hidden on that side, "…" when something is), and notes are
        # packed in one at a time, measuring as we go, until adding the next one (plus the always-
        # present bottom boundary row) would exceed `height` lines — a note's front/back text can
        # wrap across multiple lines, so a fixed row count can't be assumed. Callers showing the
        # whole deck (top_row=None) get the old compact table with no boundaries or height limit.
        windowed = top_row is not None
        top_row = max(1, min(top_row, total)) if windowed and total else 1

        show_index = total > 1

        table = Table(
            show_header=True,
            box=box.DOUBLE_EDGE,
            border_style=self.COLOR_SECONDARY,
            header_style=self.COLOR_PRIMARY + " bold",
            row_styles=[self.COLOR_PRIMARY, self.COLOR_SECONDARY],
        )
        if show_index:
            # Sized to the widest possible row number (the total note count), not just whatever's
            # visible right now, so the column doesn't resize as the user scrolls.
            table.add_column("#", width=max(len("#"), len(str(total))))
        table.add_column("☖ Front", width=col_width)
        table.add_column("☗ Back", width=col_width)
        if result:
            table.add_column(result.op_title)

        num_columns = sum([show_index, 1, 1, bool(result)])

        def add_boundary_row(show_ellipsis: bool):
            cell = "…" if show_ellipsis else ""
            table.add_row(*(Text(cell, style=self.COLOR_QUIET) for _ in range(num_columns)))

        def add_blank_row():
            table.add_row(*(Text("") for _ in range(num_columns)))

        def note_row_cells(i: int) -> list:
            note = notes[i]
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
            return row

        def add_note_row(i: int):
            table.add_row(*note_row_cells(i))

        if not windowed:
            for i in range(total):
                add_note_row(i)
            return table

        def rendered_height() -> int:
            return len(self.console.render_lines(table, self.console.options, pad=False))

        def row_height(cells: list) -> int:
            # Measuring a candidate row by re-rendering the whole table-so-far (rendered_height())
            # made packing an O(n^2) operation on tall windows. A throwaway table sharing the real
            # table's column widths/padding wraps the row's text the same way, in time proportional
            # to just that row's own content instead of everything packed before it.
            probe = Table(box=None, show_header=False, padding=table.padding)
            for column in table.columns:
                probe.add_column(width=column.width)
            probe.add_row(*cells)
            return len(self.console.render_lines(probe, self.console.options, pad=False))

        add_boundary_row(top_row > 1)

        packed_height = rendered_height()
        last_included = top_row - 2  # 0-indexed; "one before the first candidate" until proven otherwise
        i = top_row - 1
        while i < total:
            cells = note_row_cells(i)
            new_height = packed_height + row_height(cells)
            if new_height + 1 > height:  # +1 reserves the always-present bottom boundary row
                break
            table.add_row(*cells)
            packed_height = new_height
            last_included = i
            i += 1

        add_boundary_row(last_included < total - 1)

        # Record how many actual note rows were included (distinct from table.row_count, which
        # after padding below would also count blank filler rows) — fit_top_row() relies on this
        # to tell whether a given top_row's packing reaches the end of the deck.
        table.shown_notes = max(0, last_included - (top_row - 1) + 1)

        # Packing can legitimately stop with room to spare (e.g. the next note doesn't fit, or
        # the deck simply runs out near the end) — pad with blank rows so the table always
        # renders at exactly `height` lines, regardless of scroll position, so nothing shifts.
        for _ in range(max(0, height - rendered_height())):
            add_blank_row()

        return table


    def terminal_height(self) -> int:
        """The terminal's current height in lines."""
        return self.console.size.height

    def deck(self, deck: Deck, result: DeckOpResult = None, include_header: bool = True,
              top_row: int = None, max_top_row: int = None, height: int = None, col_width: int = 40,
              scrollable: bool = False, on_scroll: Callable[[int], None] = None):

        if include_header:
            self.deck_name(deck.name)
            self.deck_meta(deck.meta)

        if not self._fullscreen and not scrollable:
            self.console.print(self.deck_notes(deck, result, top_row, height, col_width))
            return

        # Keeps a single Live region open and redraws just the table+hint in place, instead of the
        # clear()+reprint the rest of interactive mode uses (which flickers on every keystroke).
        current_top_row = top_row or 1
        max_top_row = max_top_row or current_top_row
        can_scroll = scrollable and max_top_row > 1
        hint_parts = []
        if self._fullscreen:
            hint_parts.append("Enter refresh")
        if can_scroll:
            hint_parts.append("↑/↓ scroll")
        if self._fullscreen:
            hint_parts.append("Tab next tab")
        hint_parts.append("Ctrl+C exit")
        hint_text = " · ".join(hint_parts)

        def render() -> Group:
            row = current_top_row if can_scroll else None
            table = self.deck_notes(deck, result, row, height, col_width)
            return Group(table, Text(""), Text(hint_text, style="italic " + self.COLOR_QUIET))

        with Live(render(), console=self.console, auto_refresh=False, transient=False) as live:
            while True:
                key = self._read_key()
                if self._fullscreen and key in ("tab", "shift+tab"):
                    raise TabSwitch(key)
                if self._fullscreen and key == "enter":
                    return
                if can_scroll and key == "up" and current_top_row > 1:
                    current_top_row -= 1
                elif can_scroll and key == "down" and current_top_row < max_top_row:
                    current_top_row += 1
                elif can_scroll and key == "home" and current_top_row > 1:
                    current_top_row = 1
                elif can_scroll and key == "end" and current_top_row < max_top_row:
                    current_top_row = max_top_row
                else:
                    continue
                if on_scroll:
                    on_scroll(current_top_row)
                live.update(render())
                live.refresh()


    def preview(self, prompt: str, deck: Deck, result: DeckOpResult = None, height: int = None) -> bool:
        if self._fullscreen:
            return self._preview_fullscreen(prompt, deck, result, height)
        self.console.print(Text("Preview:", style=self.COLOR_PRIMARY + " bold"))
        self.deck(deck, result, include_header=False)
        return self.input(f"{prompt} (y - yes, n - no)\n").lower() == "y"


    def _preview_fullscreen(self, prompt: str, deck: Deck, result: DeckOpResult, height: int = None) -> bool:
        # `height` is the content area already available to the caller (e.g. below an on-screen
        # status bar / tab bar) — we reserve our own "Preview:"/blank/prompt/blank/hint lines
        # from it, plus 1 of slack so the table doesn't push that trailing hint off-screen.
        height = height if height is not None else self.terminal_height()
        height = max(1, height - 6)

        def fit_top_row(total: int) -> int:
            if total == 0:
                return 1
            top_row = total
            while top_row > 1:
                candidate = top_row - 1
                shown = self.deck_notes(deck, result, candidate, height).shown_notes
                if candidate + shown - 1 < total:
                    break
                top_row = candidate
            return top_row

        max_top_row = fit_top_row(len(deck.notes))
        can_scroll = max_top_row > 1
        current_top_row = 1

        hint_parts = ["Enter accept", "⌫ discard"]
        if can_scroll:
            hint_parts.append("↑/↓ scroll")
        hint_parts += ["Tab next tab", "Ctrl+C exit"]
        hint_text = " · ".join(hint_parts)

        def render() -> Group:
            row = current_top_row if can_scroll else None
            table = self.deck_notes(deck, result, row, height)
            return Group(Text("Preview:", style=self.COLOR_PRIMARY + " bold"), table, Text(""),
                         Text(prompt, style="italic " + self.COLOR_PRIMARY),
                         Text(""), Text(hint_text, style="italic " + self.COLOR_QUIET))

        with Live(render(), console=self.console, auto_refresh=False, transient=False) as live:
            while True:
                key = self._read_key()
                if key in ("tab", "shift+tab"):
                    raise TabSwitch(key)
                if key == "enter":
                    return True
                if key == "backspace":
                    return False
                if can_scroll and key == "up" and current_top_row > 1:
                    current_top_row -= 1
                elif can_scroll and key == "down" and current_top_row < max_top_row:
                    current_top_row += 1
                elif can_scroll and key == "home" and current_top_row > 1:
                    current_top_row = 1
                elif can_scroll and key == "end" and current_top_row < max_top_row:
                    current_top_row = max_top_row
                else:
                    continue
                live.update(render())
                live.refresh()


    def input(self, prompt: str) -> str:
        self.console.print(prompt, style="italic " + self.COLOR_PRIMARY, end="")
        return input()


    def _render_input_multi(self, lines: list[str], row: int, col: int, newline_hint: str = None,
                             show_hint: bool = True) -> Group:
        rendered = []
        for i, line in enumerate(lines):
            text = Text()
            text.append("❯ ", style=self.COLOR_SECONDARY + " bold")
            if i == row:
                text.append(line[:col], style="white")
                if col < len(line):
                    text.append(line[col], style="white reverse")
                    text.append(line[col + 1:], style="white")
                elif not line and newline_hint:
                    # The cursor sits on the hint's first letter instead of before it.
                    text.append(newline_hint[0], style=self.COLOR_QUIET + " reverse")
                    text.append(newline_hint[1:], style="italic " + self.COLOR_QUIET)
                else:
                    text.append(" ", style="white reverse")
            else:
                text.append(line, style="white")
                if not line and newline_hint:
                    text.append(newline_hint, style="italic " + self.COLOR_QUIET)
            rendered.append(text)

        if not show_hint:
            return Group(*rendered)

        hint_text = "Enter confirm" if row == len(lines) - 1 and not lines[row] else "Enter new line"
        hint_text += " · ⌫ delete · ←/→/↑/↓ navigate"
        if self._fullscreen:
            hint_text += " · Tab next tab"
        hint_text += " · Ctrl+C exit"
        hint = Text(hint_text, style="italic " + self.COLOR_QUIET)
        return Group(*rendered, Text(""), hint)


    def _input_multi_by_input(self) -> list[str]:
        lines = []
        while True:
            line = self.input("> ").strip()
            if not line:
                break
            lines.append(line)
        return lines


    def input_multi(self, prompt: str, newline_hint: str = None) -> list[str]:
        if prompt:
            self.console.print(prompt, style="italic " + self.COLOR_PRIMARY)

        can_read_keys = msvcrt or (termios and tty)
        if not sys.stdin.isatty() or not can_read_keys:
            return self._input_multi_by_input()

        lines = [""]
        row = 0
        col = 0
        with Live(self._render_input_multi(lines, row, col, newline_hint), console=self.console,
                  auto_refresh=False, transient=False) as live:
            while True:
                key = self._read_key()
                if self._fullscreen and key in ("tab", "shift+tab"):
                    raise TabSwitch(key)
                elif key == "left":
                    if col > 0:
                        col -= 1
                    elif row > 0:
                        row -= 1
                        col = len(lines[row])
                    else:
                        continue
                elif key == "right":
                    if col < len(lines[row]):
                        col += 1
                    elif row < len(lines) - 1:
                        row += 1
                        col = 0
                    else:
                        continue
                elif key == "up" and row > 0:
                    row -= 1
                    col = min(col, len(lines[row]))
                elif key == "down" and row < len(lines) - 1:
                    row += 1
                    col = min(col, len(lines[row]))
                elif key == "backspace":
                    if col > 0:
                        lines[row] = lines[row][:col - 1] + lines[row][col:]
                        col -= 1
                    elif row > 0:
                        col = len(lines[row - 1])
                        lines[row - 1] += lines[row]
                        del lines[row]
                        row -= 1
                    else:
                        continue
                elif key == "enter":
                    if row == len(lines) - 1 and not lines[row]:
                        del lines[row]
                        break
                    lines.insert(row + 1, lines[row][col:])
                    lines[row] = lines[row][:col]
                    row += 1
                    col = 0
                elif key is not None and len(key) == 1 and key.isprintable():
                    lines[row] = lines[row][:col] + key + lines[row][col:]
                    col += 1
                else:
                    continue
                live.update(self._render_input_multi(lines, row, col, newline_hint))
                live.refresh()

            live.update(self._render_input_multi(lines, row, col, newline_hint, show_hint=False))
            live.refresh()

        return [line for line in lines if line]


    def _read_key(self) -> Optional[str]:
        """Reads a single keypress, returning "up"/"down"/"left"/"right"/"home"/"end"/"tab"/
        "shift+tab"/"enter"/"backspace", a single printable character, or None for anything else
        (ignored). Raises KeyboardInterrupt on Ctrl+C, since raw mode otherwise swallows it
        instead of raising SIGINT."""
        if msvcrt:
            ch = msvcrt.getch()
            if ch == b"\x03":
                raise KeyboardInterrupt
            if ch in (b"\x00", b"\xe0"):
                return {b"H": "up", b"P": "down", b"M": "right", b"K": "left",
                        b"G": "home", b"O": "end", b"\x0f": "shift+tab"}.get(msvcrt.getch())
            if ch in (b"\r", b"\n"):
                return "enter"
            if ch == b"\x08":
                return "backspace"
            if ch == b"\t":
                return "tab"
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
                return {"A": "up", "B": "down", "C": "right", "D": "left",
                        "H": "home", "F": "end", "Z": "shift+tab"}.get(sys.stdin.read(1))
            if ch in ("\r", "\n"):
                return "enter"
            if ch in ("\x7f", "\x08"):
                return "backspace"
            if ch == "\t":
                return "tab"
            return ch if ch.isprintable() else None
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


    def _render_choice(self, options: list[str], selected: int, show_hint: bool = True,
                        abortable: bool = True) -> Group:
        lines = []
        for i, option in enumerate(options, 1):
            text = Text()
            if i - 1 == selected:
                text.append("● ", style=self.COLOR_ACCENT + " bold")
                text.append(f"{i}. ", style=self.COLOR_ACCENT + " bold")
                text.append(option, style=self.COLOR_ACCENT + " bold")
            else:
                text.append("○ ", style=self.COLOR_SECONDARY)
                text.append(f"{i}. ", style=self.COLOR_SECONDARY + " bold")
                text.append(option, style=self.COLOR_SECONDARY)
            lines.append(text)

        # With no options there's nothing to render here — the caller has already printed its own
        # content and hint() beforehand, and this call is just reading a key.
        if not show_hint or not options:
            return Group(*lines)

        hint_text = "Enter select"
        if abortable:
            hint_text += " · ⌫ back"
        hint_text += " · ↑/↓ navigate"
        if self._fullscreen:
            hint_text += " · Tab next tab"
        hint_text += " · Ctrl+C exit"
        hint = Text(hint_text, style="italic " + self.COLOR_QUIET)
        return Group(*lines, Text(""), hint)


    def _choice_by_input(self, options: list[str]) -> Optional[str]:
        if options:
            for i, option in enumerate(options, 1):
                text = Text()
                text.append(f"{i}. ", style=self.COLOR_SECONDARY + " bold")
                text.append(option, style=self.COLOR_SECONDARY)
                self.console.print(text)
        elif self._fullscreen:
            self.console.print(Text("Press Enter to continue, or 'n'/'p' for next/previous tab.",
                                     style="italic " + self.COLOR_QUIET))

        while True:
            answer = self.input("> ").strip()
            if self._fullscreen and answer.lower() == "n":
                raise TabSwitch("right")
            if self._fullscreen and answer.lower() == "p":
                raise TabSwitch("left")
            if options and answer.isdigit() and 1 <= int(answer) <= len(options):
                return options[int(answer) - 1]
            if not options and answer == "":
                return None
            self.error(f"Enter a number between 1 and {len(options)}." if options
                       else "Enter 'n'/'p' to switch tabs.")


    def choice(self, prompt: str, options: list[str], transient: bool = False,
               abortable: bool = True) -> Optional[str]:
        if prompt:
            self.console.print(prompt, style="italic " + self.COLOR_PRIMARY)

        can_read_keys = msvcrt or (termios and tty)
        if not sys.stdin.isatty() or not can_read_keys:
            return self._choice_by_input(options)

        selected = 0
        with Live(self._render_choice(options, selected, abortable=abortable), console=self.console,
                  auto_refresh=False, transient=transient) as live:
            while True:
                key = self._read_key()
                if key == "backspace" and abortable:
                    raise InteractiveAbort
                elif self._fullscreen and key in ("tab", "shift+tab"):
                    raise TabSwitch(key)
                elif options and key == "up":
                    selected = (selected - 1) % len(options)
                elif options and key == "down":
                    selected = (selected + 1) % len(options)
                elif key == "enter":
                    break
                elif options and key is not None and key.isdigit() and key != "0" and int(key) <= len(options):
                    selected = int(key) - 1
                    break
                else:
                    continue
                live.update(self._render_choice(options, selected, abortable=abortable))
                live.refresh()

            if not transient and options:
                live.update(self._render_choice(options, selected, show_hint=False))
                live.refresh()

        return options[selected] if options else None


    def _render_choice_multi(self, options: list[str], selected: int, checked: set[int], show_hint: bool = True,
                              abortable: bool = True) -> Group:
        lines = []
        for i, option in enumerate(options, 1):
            idx = i - 1
            box = "■ " if idx in checked else "□ "
            text = Text()
            if idx == selected:
                text.append(box, style=self.COLOR_ACCENT + " bold")
                text.append(f"{i}. ", style=self.COLOR_ACCENT + " bold")
                text.append(option, style=self.COLOR_ACCENT + " bold")
            else:
                text.append(box, style=self.COLOR_SECONDARY)
                text.append(f"{i}. ", style=self.COLOR_SECONDARY + " bold")
                text.append(option, style=self.COLOR_SECONDARY)
            lines.append(text)

        if not show_hint:
            return Group(*lines)

        hint_text = "Space toggle · Enter confirm"
        if abortable:
            hint_text += " · ⌫ back"
        hint_text += " · ↑/↓ navigate"
        if self._fullscreen:
            hint_text += " · Tab next tab"
        hint_text += " · Ctrl+C exit"
        hint = Text(hint_text, style="italic " + self.COLOR_QUIET)
        return Group(*lines, Text(""), hint)


    def _choice_multi_by_input(self, options: list[str]) -> list[str]:
        for i, option in enumerate(options, 1):
            text = Text()
            text.append(f"{i}. ", style=self.COLOR_SECONDARY + " bold")
            text.append(option, style=self.COLOR_SECONDARY)
            self.console.print(text)

        while True:
            answer = self.input("> (comma-separated numbers) ").strip()
            if self._fullscreen and answer.lower() == "n":
                raise TabSwitch("right")
            if self._fullscreen and answer.lower() == "p":
                raise TabSwitch("left")
            indices = [a.strip() for a in answer.split(",") if a.strip()]
            if indices and all(a.isdigit() and 1 <= int(a) <= len(options) for a in indices):
                return [options[int(a) - 1] for a in dict.fromkeys(indices)]
            self.error(f"Enter one or more numbers between 1 and {len(options)}, separated by commas.")


    def choice_multi(self, prompt: str, options: list[str], transient: bool = False,
                      abortable: bool = True) -> list[str]:
        if prompt:
            self.console.print(prompt, style="italic " + self.COLOR_PRIMARY)

        can_read_keys = msvcrt or (termios and tty)
        if not sys.stdin.isatty() or not can_read_keys:
            return self._choice_multi_by_input(options)

        selected = 0
        checked: set[int] = set()
        with Live(self._render_choice_multi(options, selected, checked, abortable=abortable),
                  console=self.console, auto_refresh=False, transient=transient) as live:
            while True:
                key = self._read_key()
                if key == "backspace" and abortable:
                    raise InteractiveAbort
                elif self._fullscreen and key in ("tab", "shift+tab"):
                    raise TabSwitch(key)
                elif key == "up":
                    selected = (selected - 1) % len(options)
                elif key == "down":
                    selected = (selected + 1) % len(options)
                elif key == " ":
                    checked ^= {selected}
                elif key == "enter":
                    if checked:
                        break
                    continue
                elif key is not None and key.isdigit() and key != "0" and int(key) <= len(options):
                    checked ^= {int(key) - 1}
                else:
                    continue
                live.update(self._render_choice_multi(options, selected, checked, abortable=abortable))
                live.refresh()

            if not transient:
                live.update(self._render_choice_multi(options, selected, checked, show_hint=False))
                live.refresh()

        return [options[i] for i in sorted(checked)]


    def _render_tabs(self, tab_names: list[str], current_tab: int) -> Text:
        text = Text()
        for i, name in enumerate(tab_names):
            if i > 0:
                text.append("  ")
            if i == current_tab:
                text.append(f" {name} ", style=f"black on {self.COLOR_PRIMARY} bold")
            else:
                text.append(f" {name} ", style=self.COLOR_PRIMARY)
        return text


    def tab_bar(self, tab_names: list[str], current_tab: int):
        self.console.print(self._render_tabs(tab_names, current_tab))
        self.console.print()


    def integrations(self, rows: list[tuple[str, str, Optional[str]]]):
        need_fix = sum(1 for _, _, help_text in rows if help_text)

        if need_fix:
            self.console.print(Text(f"{need_fix} integrations need repair", style=self.COLOR_WARNING + " bold"))
            self.console.print()

        for name, status, help_text in rows:
            line = Text()
            line.append(f"{name}: ", style=self.COLOR_PRIMARY + " bold")
            line.append(status, style=self.COLOR_PRIMARY)
            self.console.print(line)
            if help_text:
                self.console.print(Text(f"Repair steps: {help_text}", style=self.COLOR_QUIET))


    def deck_meta(self, meta: DeckMeta):
        items = list(meta.to_dict().items())
        for i, (key, value) in enumerate(items):
            branch = "├─ " if i < len(items) - 1 else "└─ "
            text = Text()
            text.append(f"{branch}{key}: ", style=self.COLOR_SECONDARY + " bold")
            text.append(str(value), style=self.COLOR_SECONDARY)
            self.console.print(text)


    def deck_name(self, name: str):
        text = Text()
        text.append("Deck: ", style=self.COLOR_PRIMARY + " bold")
        text.append(name, style=self.COLOR_PRIMARY)
        self.console.print(text)
