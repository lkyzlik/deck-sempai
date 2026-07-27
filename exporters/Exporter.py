from abc import ABC, abstractmethod

from Deck import Deck
from DeckOperator import DeckOperator, DeckOpResult


class Exporter(DeckOperator, ABC):
    @abstractmethod
    def export_deck(self, deck: Deck, **kwargs) -> DeckOpResult:
        pass
