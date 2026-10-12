import sys
import time
from collections import deque
from datetime import datetime
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


class _BodyProgress:
    """A LoggerProgress that renders into a fullscreen RichConsoleFrontend's shared body instead
    of managing its own Live — Rich only allows one Live per Console at a time, and the
    session-long Live from fullscreen() is already active while this runs."""
    def __init__(self, frontend: "RichConsoleFrontend"):
        self._frontend = frontend
        self._progress = Progress(
            TextColumn("{task.description}", style=frontend.COLOR_PRIMARY),
            _FlowerBarColumn(style=frontend.COLOR_PRIMARY),
            _StyledMofNCompleteColumn(style=frontend.COLOR_PRIMARY),
        )

    def __enter__(self) -> "_BodyProgress":
        self._frontend._append_body(self._progress)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._frontend._redraw()

    def add_task(self, description: str, total: int) -> int:
        task_id = self._progress.add_task(description, total=total)
        self._frontend._redraw()
        return task_id

    def update(self, task_id: int, advance: int = 0, description: str = None):
        kwargs = {} if description is None else {"description": description}
        self._progress.update(task_id, advance=advance, **kwargs)
        self._frontend._redraw()


class RichConsoleFrontend:
    COLOR_PRIMARY = "#fae9c8"
    COLOR_SECONDARY = "#a8813a"
    COLOR_ACCENT = "magenta"
    COLOR_QUIET = "grey50"
    COLOR_INFO = "blue"
    COLOR_WARNING = "yellow"
    COLOR_ERROR = "red"
    COLOR_SUCCESS = "green"

    _LOG_PREFIX = {"info": "Info: ", "warning": "Warning: ", "error": "Error: "}
    _LOG_LEVELS = {"info": 0, "warning": 1, "error": 2}

    _NOTE_STATUS_STYLE = {
        "ok": ("✓", COLOR_SUCCESS),
        "failed": ("✗", COLOR_ERROR),
        "skipped": ("↪", COLOR_INFO),
    }

    _INTEGRATION_STATUS_STYLE = {
        "running": ("●", COLOR_SUCCESS),
        "disconnected": ("✗", COLOR_ERROR),
        "disabled": ("–", COLOR_QUIET),
    }

    # Fixed heights of the chrome regions that sandwich the body in fullscreen mode: the header
    # (status_bar() + tab_bar(), each 1 line of content + 1 blank). The footer (log_window()) is
    # 5 lines (separator + 4 log lines) when visible, or just 1 (the separator) when hidden via
    # Ctrl+L — see _footer_lines().
    _HEADER_LINES = 4
    _FOOTER_LINES_VISIBLE = 5
    _FOOTER_LINES_HIDDEN = 1

    def __init__(self, console: Console = Console(), log_level: str = "warning"):
        self.console = console
        self.log_level = log_level
        # Set for the duration of fullscreen()'s `with` block — every method below checks this
        # to decide between its plain (own-Live-per-call, unchanged) behavior and the fullscreen
        # behavior (render into the shared header/body/footer composition below instead).
        self._fullscreen = False
        # The one Live that lives for the whole fullscreen() session (None outside it). Every
        # fullscreen redraw goes through _redraw(), which updates this.
        self._live: Optional[Live] = None
        # header = status_bar()/tab_bar() content; body = accumulated widget output (appended to
        # on non-transient completion, discarded on transient completion, wiped and replaced by
        # a single entry by the preview widget); log_scroll = the footer's current scroll offset.
        # All reset at the start of each fullscreen() session.
        self._header: Group = Group()
        self._header_status: Optional[Text] = None
        self._header_tabs: Optional[Text] = None
        self._body_parts: list = []
        self._log_scroll = 0
        self._log_visible = True
        # info()/warning()/error() always record here (level, message, timestamp captured at log
        # time); in fullscreen they skip the direct print and rely on log_window() to surface
        # this instead.
        self._log_buffer: deque[tuple[str, str, str]] = deque(maxlen=50)


    def _field_to_rich(self, field: Field):
        text = Text()
        text.append(field.get_text_oneline())
        for sound in field.sounds:
            text.append(Text(" [♪]"))
        return text


    def print(self, message: str):
        if self._fullscreen:
            self._append_body(Text(message, style=self.COLOR_PRIMARY))
            return
        self.console.print(message, style=self.COLOR_PRIMARY)


    @property
    def is_fullscreen(self) -> bool:
        return self._fullscreen


    @contextmanager
    def fullscreen(self) -> AbstractContextManager:
        self._fullscreen = True
        self._header = Group()
        self._header_status = None
        self._header_tabs = None
        self._body_parts = []
        self._log_scroll = 0
        self._log_visible = True
        try:
            with self.console.screen():
                with Live(self._compose_frame(), console=self.console, auto_refresh=False,
                          transient=False) as live:
                    self._live = live
                    yield
        finally:
            self._live = None
            self._fullscreen = False


    def clear(self):
        if self._fullscreen:
            self._body_parts = []
            self._redraw()
            return
        self.console.clear()


    def hint(self, message: str):
        if self._fullscreen:
            self._append_body(Group(Text(""), Text(message, style="italic " + self.COLOR_QUIET)))
            return
        self.console.print()
        self.console.print(message, style="italic " + self.COLOR_QUIET)


    def _rebuild_header(self):
        parts = []
        if self._header_status is not None:
            parts += [self._header_status, Text("")]
        if self._header_tabs is not None:
            parts += [self._header_tabs, Text("")]
        self._header = Group(*parts)
        self._redraw()


    def status_bar(self, version: str, current_deck: Deck, load_failed: bool = False):
        text = Text()
        text.append("Deck Sempai", style=self.COLOR_SECONDARY + " bold")
        text.append(f" · v{version} · Current deck: ", style=self.COLOR_SECONDARY)
        text.append(current_deck.name, style=self.COLOR_SECONDARY + " bold")
        cards = "?" if load_failed else len(current_deck.notes)
        text.append(f" ({cards} cards)", style=self.COLOR_SECONDARY)
        if not self._fullscreen:
            self.console.print(text)
            self.console.print()
            return
        self._header_status = text
        self._rebuild_header()


    @staticmethod
    def _timestamp() -> str:
        return datetime.now().strftime("%H:%M:%S")


    def _should_log(self, level: str) -> bool:
        return self._LOG_LEVELS[level] >= self._LOG_LEVELS.get(self.log_level, 0)


    def info(self, message: str):
        if not self._should_log("info"):
            return
        self._log_buffer.append(("info", message, self._timestamp()))
        if self._fullscreen:
            return
        text = Text()
        text.append("Info: ", style="bold " + self.COLOR_INFO)
        text.append(message, style=self.COLOR_INFO)
        self.console.print(text)


    def error(self, message: str):
        if not self._should_log("error"):
            return
        self._log_buffer.append(("error", message, self._timestamp()))
        if self._fullscreen:
            return
        text = Text()
        text.append("Error: ", style="bold " + self.COLOR_ERROR)
        text.append(message, style=self.COLOR_ERROR)
        self.console.print(text)


    def warning(self, message: str):
        if not self._should_log("warning"):
            return
        self._log_buffer.append(("warning", message, self._timestamp()))
        if self._fullscreen:
            return
        text = Text()
        text.append("Warning: ", style="bold " + self.COLOR_WARNING)
        text.append(message, style=self.COLOR_WARNING)
        self.console.print(text)


    def progress(self) -> LoggerProgress:
        if self._fullscreen:
            return _BodyProgress(self)
        return Progress(
            TextColumn("{task.description}", style=self.COLOR_PRIMARY),
            _FlowerBarColumn(style=self.COLOR_PRIMARY),
            _StyledMofNCompleteColumn(style=self.COLOR_PRIMARY),
            console=self.console
        )


    def log_window(self, scroll_offset: int = 0) -> Group:
        hint = "Ctrl+L show logs" if not self._log_visible else "PgUp/PgDn scroll · Ctrl+L hide logs"
        width = self.console.width
        trailing = 3
        leading = max(0, width - len(hint) - trailing)
        separator = Text("─" * leading, style=self.COLOR_QUIET, no_wrap=True, overflow="crop")
        separator.append(hint, style="italic " + self.COLOR_QUIET)
        separator.append("─" * trailing, style=self.COLOR_QUIET)

        if not self._log_visible:
            return Group(separator)

        colors = {"info": self.COLOR_INFO, "warning": self.COLOR_WARNING, "error": self.COLOR_ERROR}
        max_offset = max(0, len(self._log_buffer) - 4)
        scroll_offset = max(0, min(scroll_offset, max_offset))
        end = len(self._log_buffer) - scroll_offset
        entries = list(self._log_buffer)[max(0, end - 4):end]

        lines = [Text("") for _ in range(4 - len(entries))]
        for level, message, timestamp in entries:
            text = Text(no_wrap=True, overflow="crop")
            text.append(timestamp + " ", style=self.COLOR_QUIET)
            text.append(self._LOG_PREFIX[level], style="bold " + colors[level])
            text.append(message, style=colors[level])
            lines.append(text)
        return Group(separator, *lines)


    def _footer_lines(self) -> int:
        return self._FOOTER_LINES_VISIBLE if self._log_visible else self._FOOTER_LINES_HIDDEN


    def deck_notes(self, deck: Deck, result: DeckOpResult = None, top_row: int = None, height: int = None,
                   col_width: int = 30) -> Table:
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
            table.add_column("Result")

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
                symbol, style = self._NOTE_STATUS_STYLE[note_result.status]
                row.append(Text(f"{symbol} {note_result.status}", style=style))
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


    def _available_body_height(self) -> int:
        """How many lines a fullscreen widget's own content can use, below the persistent status
        bar/tab bar and above the log window (more, while the log window is hidden)."""
        return max(0, self.terminal_height() - self._HEADER_LINES - self._footer_lines())


    def _redraw(self):
        if self._live is not None:
            self._live.update(self._compose_frame())
            self._live.refresh()


    def _append_body(self, renderable):
        self._body_parts.append(renderable)
        self._redraw()


    def _compose_body(self, available: int) -> Group:
        # Keeps the newest accumulated widgets that fit in `available` lines, dropping older ones
        # whole (never mid-entry) once there's no more room — like a terminal that scrolls old
        # content off the top while the newest stays put, so the footer below is never pushed.
        kept = []
        total = 0
        for part in reversed(self._body_parts):
            part_height = len(self.console.render_lines(part, self.console.options, pad=False))
            if total + part_height > available:
                break
            kept.insert(0, part)
            total += part_height
        padding = [Text("") for _ in range(max(0, available - total))]
        return Group(*kept, *padding)


    def _compose_frame(self) -> Group:
        body = self._compose_body(self._available_body_height())
        return Group(self._header, body, self.log_window(self._log_scroll))


    def deck(self, deck: Deck, result: DeckOpResult = None, include_header: bool = True,
              top_row: int = None, max_top_row: int = None, height: int = None, col_width: int = 30,
              scrollable: bool = False, on_scroll: Callable[[int], None] = None):

        if include_header:
            self.deck_name(deck.name)
            self.deck_meta(deck.meta)

        if self._fullscreen:
            return self._deck_fullscreen(deck, result, top_row, col_width, scrollable, on_scroll)

        if not scrollable:
            self.console.print(self.deck_notes(deck, result, top_row, height, col_width))
            return

        # Scrollable outside fullscreen is a rare combo (no current caller uses it), kept for API
        # completeness with its own short-lived Live, same as every widget used to work before.
        current_top_row = top_row or 1
        max_top_row = max_top_row or current_top_row
        can_scroll = max_top_row > 1
        hint_parts = []
        if can_scroll:
            hint_parts.append("↑/↓ scroll")
        hint_parts.append("Ctrl+C exit")
        hint_text = " · ".join(hint_parts)

        def render() -> Group:
            row = current_top_row if can_scroll else None
            table = self.deck_notes(deck, result, row, height, col_width)
            return Group(table, Text(""), Text(hint_text, style="italic " + self.COLOR_QUIET))

        with Live(render(), console=self.console, auto_refresh=False, transient=False) as live:
            while True:
                key = self._read_key()
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


    def _deck_fullscreen(self, deck: Deck, result: DeckOpResult, top_row: int, col_width: int,
                          scrollable: bool, on_scroll: Callable[[int], None]):
        # -3 reserves the blank line + hint line this entry adds below the table, plus 1 of
        # slack so it doesn't exactly fill (and risk overflowing) the available body height.
        height = max(1, self._available_body_height() - 3)

        def fit_top_row(total: int) -> int:
            if total == 0:
                return 1
            candidate_top = total
            while candidate_top > 1:
                candidate = candidate_top - 1
                shown = self.deck_notes(deck, result, candidate, height).shown_notes
                if candidate + shown - 1 < total:
                    break
                candidate_top = candidate
            return candidate_top

        max_top_row = fit_top_row(len(deck.notes)) if scrollable else 1
        can_scroll = scrollable and max_top_row > 1
        # No remembered position (first time showing this tab) defaults to the end of the deck;
        # otherwise clamp in case the deck shrank/grew since the remembered position was set.
        current_top_row = max_top_row if top_row is None else max(1, min(top_row, max_top_row))
        if on_scroll:
            on_scroll(current_top_row)

        hint_parts = ["Enter refresh"]
        if can_scroll:
            hint_parts.append("↑/↓ scroll")
        hint_parts += ["Tab next tab", "Ctrl+C exit"]
        hint_text = " · ".join(hint_parts)

        def render_entry() -> Group:
            row = current_top_row if can_scroll else None
            table = self.deck_notes(deck, result, row, height, col_width)
            return Group(table, Text(""), Text(hint_text, style="italic " + self.COLOR_QUIET))

        self._body_parts.append(render_entry())
        self._redraw()
        while True:
            key = self._read_key()
            if key in ("tab", "shift+tab", "left", "right"):
                raise TabSwitch(key)
            if key == "enter":
                return
            scrolled = False
            if can_scroll and key == "up" and current_top_row > 1:
                current_top_row -= 1
                scrolled = True
            elif can_scroll and key == "down" and current_top_row < max_top_row:
                current_top_row += 1
                scrolled = True
            elif can_scroll and key == "home" and current_top_row > 1:
                current_top_row = 1
                scrolled = True
            elif can_scroll and key == "end" and current_top_row < max_top_row:
                current_top_row = max_top_row
                scrolled = True
            elif key == "pageup":
                self._log_scroll = min(self._log_scroll + 1, max(0, len(self._log_buffer) - 4))
            elif key == "pagedown":
                self._log_scroll = max(0, self._log_scroll - 1)
            elif key == "ctrl+l":
                self._log_visible = not self._log_visible
            else:
                continue
            if scrolled and on_scroll:
                on_scroll(current_top_row)
            self._body_parts[-1] = render_entry()
            self._redraw()


    def preview(self, prompt: str, deck: Deck, result: DeckOpResult = None) -> bool:
        if self._fullscreen:
            return self._preview_fullscreen(prompt, deck, result)
        title = f"{result.op_title}. Preview:" if result else "Preview:"
        self.console.print(Text(title, style=self.COLOR_PRIMARY))
        self.deck(deck, result, include_header=False)
        return self.input(f"{prompt} (y - yes, n - no)\n").lower() == "y"


    def _preview_fullscreen(self, prompt: str, deck: Deck, result: DeckOpResult) -> bool:
        # The preview takes over the whole body, replacing whatever was accumulated before it.
        self._body_parts = []
        # -6 reserves "Preview:"/blank/prompt/blank/hint (5 lines) plus 1 of slack so the entry
        # doesn't exactly fill (and risk overflowing) the available body height.
        table_height = max(1, self._available_body_height() - 6)

        def fit_top_row(total: int) -> int:
            if total == 0:
                return 1
            top_row = total
            while top_row > 1:
                candidate = top_row - 1
                shown = self.deck_notes(deck, result, candidate, table_height).shown_notes
                if candidate + shown - 1 < total:
                    break
                top_row = candidate
            return top_row

        max_top_row = fit_top_row(len(deck.notes))
        can_scroll = max_top_row > 1
        current_top_row = 1

        title = f"{result.op_title}. Preview:" if result else "Preview:"

        hint_parts = ["Enter accept", "⌫ discard"]
        if can_scroll:
            hint_parts.append("↑/↓ scroll")
        hint_parts += ["Tab next tab", "Ctrl+C exit"]
        hint_text = " · ".join(hint_parts)

        def render_entry() -> Group:
            row = current_top_row if can_scroll else None
            table = self.deck_notes(deck, result, row, table_height)
            return Group(Text(title, style=self.COLOR_PRIMARY), table, Text(""),
                         Text(prompt, style="italic " + self.COLOR_PRIMARY),
                         Text(""), Text(hint_text, style="italic " + self.COLOR_QUIET))

        self._body_parts = [render_entry()]
        self._redraw()
        while True:
            key = self._read_key()
            if key in ("tab", "shift+tab", "left", "right"):
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
            elif key == "pageup":
                self._log_scroll = min(self._log_scroll + 1, max(0, len(self._log_buffer) - 4))
            elif key == "pagedown":
                self._log_scroll = max(0, self._log_scroll - 1)
            elif key == "ctrl+l":
                self._log_visible = not self._log_visible
            else:
                continue
            self._body_parts[-1] = render_entry()
            self._redraw()


    def _render_input(self, text: str, col: int, show_hint: bool = True) -> Group:
        line = Text()
        line.append("❯ ", style=self.COLOR_ACCENT + " bold")
        line.append(text[:col], style="white")
        if col < len(text):
            line.append(text[col], style="white reverse")
            line.append(text[col + 1:], style="white")
        else:
            line.append(" ", style="white reverse")

        if not show_hint:
            return Group(line)

        hint_text = "Enter confirm"
        if text:
            hint_text += " · ⌫ delete · ←/→ navigate"
        if self._fullscreen:
            hint_text += " · Tab next tab"
        hint_text += " · Ctrl+C exit"
        hint = Text(hint_text, style="italic " + self.COLOR_QUIET)
        return Group(line, Text(""), hint)


    def input(self, prompt: str) -> str:
        can_read_keys = msvcrt or (termios and tty)
        if not sys.stdin.isatty() or not can_read_keys:
            self.console.print(prompt, style="italic " + self.COLOR_PRIMARY, end="")
            return input()

        if self._fullscreen:
            return self._input_fullscreen(prompt)

        if prompt:
            self.console.print(prompt, style="italic " + self.COLOR_PRIMARY, end="")

        text = ""
        col = 0
        with Live(self._render_input(text, col, show_hint=False), console=self.console,
                  auto_refresh=False, transient=False) as live:
            while True:
                key = self._read_key()
                if key == "left" and col > 0:
                    col -= 1
                elif key == "right" and col < len(text):
                    col += 1
                elif key == "backspace" and col > 0:
                    text = text[:col - 1] + text[col:]
                    col -= 1
                elif key == "enter":
                    break
                elif key is not None and len(key) == 1 and key.isprintable():
                    text = text[:col] + key + text[col:]
                    col += 1
                else:
                    continue
                live.update(self._render_input(text, col, show_hint=False))
                live.refresh()

        return text


    def _input_fullscreen(self, prompt: str) -> str:
        if prompt:
            # Callers pass a trailing "\n" (matching the non-fullscreen path's `end=""` print);
            # a Text with an embedded newline renders as its own extra blank line, so strip it.
            self._append_body(Text(prompt.rstrip("\n"), style="italic " + self.COLOR_PRIMARY))

        text = ""
        col = 0
        self._body_parts.append(self._render_input(text, col))
        self._redraw()
        while True:
            key = self._read_key()
            if key in ("tab", "shift+tab"):
                raise TabSwitch(key)
            elif key == "left" and col > 0:
                col -= 1
            elif key == "right" and col < len(text):
                col += 1
            elif key == "backspace" and col > 0:
                text = text[:col - 1] + text[col:]
                col -= 1
            elif key == "enter":
                break
            elif key is not None and len(key) == 1 and key.isprintable():
                text = text[:col] + key + text[col:]
                col += 1
            elif key == "pageup":
                self._log_scroll = min(self._log_scroll + 1, max(0, len(self._log_buffer) - 4))
            elif key == "pagedown":
                self._log_scroll = max(0, self._log_scroll - 1)
            elif key == "ctrl+l":
                self._log_visible = not self._log_visible
            else:
                continue
            self._body_parts[-1] = self._render_input(text, col)
            self._redraw()

        self._body_parts[-1] = self._render_input(text, col, show_hint=False)
        self._redraw()
        return text


    def _render_input_multi(self, lines: list[str], row: int, col: int, newline_hint: str = None,
                             show_hint: bool = True) -> Group:
        rendered = []
        for i, line in enumerate(lines):
            text = Text()
            text.append("❯ ", style=(self.COLOR_ACCENT if i == row else self.COLOR_SECONDARY) + " bold")
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

        no_input_yet = len(lines) == 1 and not lines[0]
        hint_text = "Enter confirm" if row == len(lines) - 1 and not lines[row] else "Enter new line"
        if not no_input_yet:
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
        can_read_keys = msvcrt or (termios and tty)
        if not sys.stdin.isatty() or not can_read_keys:
            if prompt:
                self.console.print(prompt, style="italic " + self.COLOR_PRIMARY)
            return self._input_multi_by_input()

        if self._fullscreen:
            return self._input_multi_fullscreen(prompt, newline_hint)

        if prompt:
            self.console.print(prompt, style="italic " + self.COLOR_PRIMARY)

        lines = [""]
        row = 0
        col = 0
        with Live(self._render_input_multi(lines, row, col, newline_hint), console=self.console,
                  auto_refresh=False, transient=False) as live:
            while True:
                key = self._read_key()
                if key in ("left", "right", "up", "down") and len(lines) == 1 and not lines[0]:
                    continue
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


    def _input_multi_fullscreen(self, prompt: str, newline_hint: str) -> list[str]:
        if prompt:
            self._append_body(Text(prompt, style="italic " + self.COLOR_PRIMARY))

        lines = [""]
        row = 0
        col = 0
        self._body_parts.append(self._render_input_multi(lines, row, col, newline_hint))
        self._redraw()
        while True:
            key = self._read_key()
            if key in ("tab", "shift+tab"):
                raise TabSwitch(key)
            elif key == "pageup":
                self._log_scroll = min(self._log_scroll + 1, max(0, len(self._log_buffer) - 4))
            elif key == "pagedown":
                self._log_scroll = max(0, self._log_scroll - 1)
            elif key == "ctrl+l":
                self._log_visible = not self._log_visible
            elif key in ("left", "right") and len(lines) == 1 and not lines[0]:
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
            self._body_parts[-1] = self._render_input_multi(lines, row, col, newline_hint)
            self._redraw()

        self._body_parts[-1] = self._render_input_multi(lines, row, col, newline_hint, show_hint=False)
        self._redraw()
        return [line for line in lines if line]


    def _read_key(self) -> Optional[str]:
        """Reads a single keypress, returning "up"/"down"/"left"/"right"/"home"/"end"/"pageup"/
        "pagedown"/"tab"/"shift+tab"/"enter"/"backspace"/"ctrl+l", a single printable character,
        or None for anything else (ignored). Raises KeyboardInterrupt on Ctrl+C, since raw mode
        otherwise swallows it instead of raising SIGINT."""
        if msvcrt:
            ch = msvcrt.getch()
            if ch == b"\x03":
                raise KeyboardInterrupt
            if ch in (b"\x00", b"\xe0"):
                return {b"H": "up", b"P": "down", b"M": "right", b"K": "left",
                        b"G": "home", b"O": "end", b"I": "pageup", b"Q": "pagedown",
                        b"\x0f": "shift+tab"}.get(msvcrt.getch())
            if ch in (b"\r", b"\n"):
                return "enter"
            if ch == b"\x08":
                return "backspace"
            if ch == b"\t":
                return "tab"
            if ch == b"\x0c":
                return "ctrl+l"
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
                # CSI sequences for plain arrows/home/end are a single final letter (e.g. "A");
                # PageUp/PageDown add digits before a "~" terminator (e.g. "5~"). Accumulate
                # digits until a non-digit arrives, so either shape is fully consumed from stdin
                # (leaving a partial sequence unread would corrupt the next _read_key() call).
                digits = ""
                for _ in range(4):
                    c = sys.stdin.read(1)
                    if c.isdigit():
                        digits += c
                        continue
                    break
                else:
                    return None
                if c == "~":
                    return {"5": "pageup", "6": "pagedown"}.get(digits)
                if not digits:
                    return {"A": "up", "B": "down", "C": "right", "D": "left",
                            "H": "home", "F": "end", "Z": "shift+tab"}.get(c)
                return None
            if ch in ("\r", "\n"):
                return "enter"
            if ch in ("\x7f", "\x08"):
                return "backspace"
            if ch == "\t":
                return "tab"
            if ch == "\x0c":
                return "ctrl+l"
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
        can_read_keys = msvcrt or (termios and tty)
        if not sys.stdin.isatty() or not can_read_keys:
            if prompt:
                self.console.print(prompt, style="italic " + self.COLOR_PRIMARY)
            return self._choice_by_input(options)

        if self._fullscreen:
            return self._choice_fullscreen(prompt, options, transient, abortable)

        if prompt:
            self.console.print(prompt, style="italic " + self.COLOR_PRIMARY)

        selected = 0
        with Live(self._render_choice(options, selected, abortable=abortable), console=self.console,
                  auto_refresh=False, transient=transient) as live:
            while True:
                key = self._read_key()
                if key == "backspace" and abortable:
                    raise InteractiveAbort
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


    def _choice_fullscreen(self, prompt: str, options: list[str], transient: bool,
                            abortable: bool) -> Optional[str]:
        if prompt:
            self._append_body(Text(prompt, style="italic " + self.COLOR_PRIMARY))

        selected = 0
        self._body_parts.append(self._render_choice(options, selected, abortable=abortable))
        self._redraw()
        while True:
            key = self._read_key()
            if key == "backspace" and abortable:
                raise InteractiveAbort
            elif key in ("tab", "shift+tab", "left", "right"):
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
            elif key == "pageup":
                self._log_scroll = min(self._log_scroll + 1, max(0, len(self._log_buffer) - 4))
            elif key == "pagedown":
                self._log_scroll = max(0, self._log_scroll - 1)
            elif key == "ctrl+l":
                self._log_visible = not self._log_visible
            else:
                continue
            self._body_parts[-1] = self._render_choice(options, selected, abortable=abortable)
            self._redraw()

        if transient:
            self._body_parts.pop()
        else:
            self._body_parts[-1] = self._render_choice(options, selected, show_hint=False)
        self._redraw()
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
        can_read_keys = msvcrt or (termios and tty)
        if not sys.stdin.isatty() or not can_read_keys:
            if prompt:
                self.console.print(prompt, style="italic " + self.COLOR_PRIMARY)
            return self._choice_multi_by_input(options)

        if self._fullscreen:
            return self._choice_multi_fullscreen(prompt, options, transient, abortable)

        if prompt:
            self.console.print(prompt, style="italic " + self.COLOR_PRIMARY)

        selected = 0
        checked: set[int] = set()
        with Live(self._render_choice_multi(options, selected, checked, abortable=abortable),
                  console=self.console, auto_refresh=False, transient=transient) as live:
            while True:
                key = self._read_key()
                if key == "backspace" and abortable:
                    raise InteractiveAbort
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


    def _choice_multi_fullscreen(self, prompt: str, options: list[str], transient: bool,
                                  abortable: bool) -> list[str]:
        if prompt:
            self._append_body(Text(prompt, style="italic " + self.COLOR_PRIMARY))

        selected = 0
        checked: set[int] = set()
        self._body_parts.append(self._render_choice_multi(options, selected, checked, abortable=abortable))
        self._redraw()
        while True:
            key = self._read_key()
            if key == "backspace" and abortable:
                raise InteractiveAbort
            elif key in ("tab", "shift+tab", "left", "right"):
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
            elif key == "pageup":
                self._log_scroll = min(self._log_scroll + 1, max(0, len(self._log_buffer) - 4))
            elif key == "pagedown":
                self._log_scroll = max(0, self._log_scroll - 1)
            elif key == "ctrl+l":
                self._log_visible = not self._log_visible
            else:
                continue
            self._body_parts[-1] = self._render_choice_multi(options, selected, checked, abortable=abortable)
            self._redraw()

        if transient:
            self._body_parts.pop()
        else:
            self._body_parts[-1] = self._render_choice_multi(options, selected, checked, show_hint=False)
        self._redraw()
        return [options[i] for i in sorted(checked)]


    def _render_tabs(self, tab_names: list[str], current_tab: int) -> Text:
        text = Text()
        for i, name in enumerate(tab_names):
            if i > 0:
                text.append("  ")
            if i == current_tab:
                text.append(f" {name} ", style=f"black on {self.COLOR_ACCENT} bold")
            else:
                text.append(f" {name} ", style=self.COLOR_PRIMARY)
        return text


    def tab_bar(self, tab_names: list[str], current_tab: int):
        tabs = self._render_tabs(tab_names, current_tab)
        if not self._fullscreen:
            self.console.print(tabs)
            self.console.print()
            return
        self._header_tabs = tabs
        self._rebuild_header()


    def integrations(self, rows: list[tuple[str, str, Optional[str]]]):
        parts = []

        for name, status, help_text in rows:
            icon, color = self._INTEGRATION_STATUS_STYLE.get(status, ("?", self.COLOR_PRIMARY))
            line = Text()
            line.append(f"{name}: ", style=self.COLOR_PRIMARY + " bold")
            line.append(f"{icon} ", style=color + " bold")
            line.append(status, style=color)
            parts.append(line)
            if help_text:
                parts.append(Text(f"Repair steps:\n{help_text}", style=self.COLOR_QUIET))

        if self._fullscreen:
            self._append_body(Group(*parts))
            return
        for part in parts:
            self.console.print(part)


    def deck_meta(self, meta: DeckMeta):
        items = list(meta.to_dict().items())
        lines = []
        for i, (key, value) in enumerate(items):
            branch = "├─ " if i < len(items) - 1 else "└─ "
            text = Text()
            text.append(f"{branch}{key}: ", style=self.COLOR_SECONDARY + " bold")
            text.append(str(value), style=self.COLOR_SECONDARY)
            lines.append(text)

        if self._fullscreen:
            self._append_body(Group(*lines))
            return
        for line in lines:
            self.console.print(line)


    def deck_name(self, name: str):
        text = Text()
        text.append("Deck: ", style=self.COLOR_PRIMARY + " bold")
        text.append(name, style=self.COLOR_PRIMARY)
        if self._fullscreen:
            self._append_body(text)
            return
        self.console.print(text)
