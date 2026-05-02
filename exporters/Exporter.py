from abc import ABC, abstractmethod

from Deck import Deck
from DeckOperator import DeckOperator, DeckOpResult


class Exporter(DeckOperator, ABC):
    @abstractmethod
    def export_deck(self, deck: Deck, **kwargs) -> DeckOpResult:
        pass


class ResultsExporter(Exporter):
    @abstractmethod
    def export_deck_with_results(self, deck: Deck, result: DeckOpResult, **kwargs) -> DeckOpResult:
        pass