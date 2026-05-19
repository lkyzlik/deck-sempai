from abc import ABC, abstractmethod

from Deck import Deck, DeckMeta
from DeckOperator import DeckOperator, DeckOpResult


class Exporter(DeckOperator, ABC):
    @abstractmethod
    def export_deck(self, deck: Deck, include_metadata: bool = True, **kwargs) -> DeckOpResult:
        pass


class ShowExporter(Exporter):
    @abstractmethod
    def export_deck_with_results(self, deck: Deck, result: DeckOpResult,
                                 include_metadata: bool = True, **kwargs) -> DeckOpResult:
        pass

    @abstractmethod
    def export_deck_metadata(self, name: str, meta: DeckMeta, **kwargs) -> bool:
        pass

    @abstractmethod
    def export_deck_name(self, name: str, **kwargs) -> bool:
        pass
