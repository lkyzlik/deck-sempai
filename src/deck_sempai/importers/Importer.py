from abc import ABC, abstractmethod

from deck_sempai.Deck import Deck
from deck_sempai.DeckOperator import DeckOperator


class Importer(DeckOperator, ABC):
    @abstractmethod
    def import_deck(self, **kwargs) -> Deck:
        pass