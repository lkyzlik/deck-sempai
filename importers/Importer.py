from abc import ABC, abstractmethod

from Deck import Deck
from DeckOperator import DeckOperator


class Importer(DeckOperator, ABC):
    @abstractmethod
    def import_deck(self, **kwargs) -> Deck:
        pass