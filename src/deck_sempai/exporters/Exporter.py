from abc import ABC, abstractmethod

from deck_sempai.Deck import Deck
from deck_sempai.DeckOperator import DeckOperator, DeckOpResult


class Exporter(DeckOperator, ABC):
    @abstractmethod
    def export_deck(self, deck: Deck, **kwargs) -> DeckOpResult:
        pass
