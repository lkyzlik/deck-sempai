from abc import ABC, abstractmethod

from deck_sempai.Deck import Deck
from deck_sempai.DeckOperator import DeckOperator, DeckOpResult


class Transformer(DeckOperator, ABC):
    @abstractmethod
    def transform_deck(self, deck: Deck, **kwargs) -> DeckOpResult:
        pass