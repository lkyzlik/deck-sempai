from abc import ABC, abstractmethod

from Deck import Deck
from DeckOperator import DeckOperator, DeckOpResult


class Transformer(DeckOperator, ABC):
    @abstractmethod
    def transform_deck(self, deck: Deck, **kwargs) -> DeckOpResult:
        pass