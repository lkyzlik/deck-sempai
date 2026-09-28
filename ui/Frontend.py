from contextlib import AbstractContextManager
from typing import Protocol

from Deck import Deck, DeckMeta
from DeckOperator import DeckOpResult

from ui.Logger import Logger


class InteractiveAbort(Exception):
    pass


class Frontend(Logger, Protocol):
    def fullscreen(self) -> AbstractContextManager:
        ...

    def clear(self):
        ...

    def hint(self, message: str):
        ...

    def status_bar(self, version: str, current_deck: Deck):
        ...

    def show_deck(self, deck: Deck, result: DeckOpResult = None, include_metadata: bool = True, **kwargs):
        ...

    def show_deck_name(self, name: str, **kwargs):
        ...

    def show_deck_metadata(self, meta: DeckMeta, **kwargs):
        ...

    def preview(self, prompt: str, deck: Deck, result: DeckOpResult = None) -> str:
        ...

    def input(self, prompt: str) -> str:
        ...

    def input_multiline(self, prompt: str) -> list[str]:
        ...

    def choice(self, prompt: str, options: list[str], transient: bool = False, abortable: bool = True) -> str:
        ...

    def multi_choice(self, prompt: str, options: list[str], transient: bool = False, abortable: bool = True) -> list[str]:
        ...
