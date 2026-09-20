from typing import Protocol

from Deck import Deck, DeckMeta
from DeckOperator import DeckOpResult

from ui.Logger import Logger


class Frontend(Logger, Protocol):
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
