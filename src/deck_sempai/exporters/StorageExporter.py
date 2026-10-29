from abc import ABC, abstractmethod

from deck_sempai.Deck import Deck
from deck_sempai.DeckOperator import DeckOpResult
from deck_sempai.exporters.Exporter import Exporter


class StorageExporter(Exporter, ABC):
    """Exporting to permanent storage also involves managing the stored decks."""

    @abstractmethod
    def remove_notes(self, deck: Deck) -> DeckOpResult:
        """Removes the given notes from the deck of the same name, never the deck itself."""
        pass

    @abstractmethod
    def remove_deck(self, name: str) -> None:
        pass

    @abstractmethod
    def get_decks(self) -> list[str]:
        pass
