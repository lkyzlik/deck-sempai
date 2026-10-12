from contextlib import AbstractContextManager
from typing import Callable, Protocol, runtime_checkable

from Deck import Deck
from DeckOperator import DeckOpResult

from ui.Frontend import Frontend


class TabSwitch(Exception):
    """Raised by TuiFrontend's choice()/choice_multi()/input_multi()/deck()/preview() (while the
    frontend is in fullscreen mode) when Tab/Shift+Tab is pressed, or Left/Right is pressed and
    not consumed by the active widget. `key` is "tab"/"right" (next tab) or "shift+tab"/"left"
    (previous tab). Only TuiApp's tabbed loop catches this, so it lives with TuiFrontend rather
    than the plain Frontend."""
    def __init__(self, key: str):
        self.key = key


@runtime_checkable
class TuiFrontend(Frontend, Protocol):
    """Adds what only TuiApp's full-screen tabbed mode needs on top of Frontend. Declared
    @runtime_checkable so TuiApp.tui() can do `isinstance(self.frontend, TuiFrontend)` to check
    the configured frontend actually supports the TUI before using it."""

    def fullscreen(self) -> AbstractContextManager:
        ...

    @property
    def is_fullscreen(self) -> bool:
        ...

    def clear(self):
        ...

    def hint(self, message: str):
        ...

    def status_bar(self, version: str, current_deck: Deck, load_failed: bool = False):
        ...

    def tab_bar(self, tab_names: list[str], current_tab: int):
        ...

    def integrations(self, rows: list[tuple[str, str, str | None]]):
        ...

    def deck_notes(self, deck: Deck, result: DeckOpResult = None, top_row: int = None, height: int = None,
                   col_width: int = 40) -> object:
        ...

    def terminal_height(self) -> int:
        ...

    def log_window(self, scroll_offset: int = 0) -> object:
        ...

    def deck(self, deck: Deck, result: DeckOpResult = None, include_header: bool = True,
             top_row: int = None, max_top_row: int = None, height: int = None, col_width: int = 40,
             scrollable: bool = False, on_scroll: Callable[[int], None] = None):
        ...

    def choice(self, prompt: str, options: list[str], transient: bool = False,
               abortable: bool = True) -> str | None:
        ...

    def choice_multi(self, prompt: str, options: list[str], transient: bool = False,
                      abortable: bool = True) -> list[str]:
        ...
