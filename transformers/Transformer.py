from abc import ABC, abstractmethod

from Deck import Deck


class Transformer(ABC):
    name: str

    @abstractmethod
    def transform_deck(self, deck: Deck, *args) -> Deck:
        pass


class TransformerError(Exception):
    def __init__(self, transformer: Transformer, message: str):
        super().__init__(f'{transformer.name!r} transformer: {message}')