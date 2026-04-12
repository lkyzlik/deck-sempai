from abc import ABC, abstractmethod

from Deck import Deck


class Importer(ABC):
    name: str

    @abstractmethod
    def import_deck(self, **kwargs) -> Deck:
        pass


class ImporterError(Exception):
    def __init__(self, importer: Importer, message: str):
        super().__init__(f'{importer.name!r} importer: {message}')