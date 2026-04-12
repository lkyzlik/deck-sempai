from abc import ABC, abstractmethod

from Deck import Deck
from Results import DeckOpResult


class Exporter(ABC):
    name: str

    @abstractmethod
    def export_deck(self, deck: Deck, **kwargs) -> DeckOpResult:
        pass


class ResultsExporter(Exporter):
    @abstractmethod
    def export_deck_with_results(self, deck: Deck, result: DeckOpResult, **kwargs) -> DeckOpResult:
        pass


class ExporterError(Exception):
    def __init__(self, exporter: Exporter, message: str):
        super().__init__(f'{exporter.name!r} exporter: {message}')