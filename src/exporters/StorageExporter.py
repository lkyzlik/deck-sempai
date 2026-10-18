from abc import ABC, abstractmethod

from exporters.Exporter import Exporter


class StorageExporter(Exporter, ABC):
    @abstractmethod
    def create_deck(self, name: str) -> None:
        pass

    @abstractmethod
    def delete_deck(self, name: str) -> None:
        pass

    @abstractmethod
    def get_decks(self) -> list[str]:
        pass
