from abc import ABC, abstractmethod

from Deck import Deck


class Exporter(ABC):
    name: str

    @abstractmethod
    def export_deck(self, deck: Deck, *args) -> None:
        pass


class ExporterError(Exception):
    def __init__(self, exporter: Exporter, message: str):
        super().__init__(f'{exporter.name!r} exporter: {message}')