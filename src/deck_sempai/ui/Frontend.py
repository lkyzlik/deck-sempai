from typing import Protocol

from deck_sempai.Deck import Deck, DeckMeta
from deck_sempai.DeckOperator import DeckOpResult

from deck_sempai.ui.Logger import Logger


class InteractiveAbort(Exception):
    pass


class Frontend(Logger, Protocol):
    def choice(self, prompt: str, options: list[str], abortable: bool = True) -> str | None:
        ...

    def choice_multi(self, prompt: str, options: list[str], abortable: bool = True) -> list[str]:
        ...

    def input(self, prompt: str) -> str:
        ...

    def input_multi(self, prompt: str, newline_hint: str = None) -> list[str]:
        ...

    def deck(self, deck: Deck, result: DeckOpResult = None, include_header: bool = True,
             col_width: int = 40):
        ...

    def deck_name(self, name: str):
        ...

    def deck_meta(self, meta: DeckMeta):
        ...

    def preview(self, prompt: str, deck: Deck, result: DeckOpResult = None) -> bool:
        ...
