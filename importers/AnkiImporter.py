from integrations.AnkiIntegration import AnkiIntegration, AnkiIntegrationError, AnkiIntegrationDisabledError
from Deck import Deck, DeckMeta, Field, Note
from DeckOperator import DeckOpError
from importers.Importer import Importer

from interfaces.Logger import Logger


class AnkiImporter(Importer):
    def __init__(self, logger: Logger, ac: AnkiIntegration):
        super().__init__(logger)
        self.ac = ac


    def _import_deck(self, deck_name: str) -> Deck:
        deck = Deck(deck_name)

        try:
            note_ids: list = self.ac.find_notes(f'deck:{deck.name}')
            notes_info: list  = self.ac.notes_info(note_ids)
            metadata: dict = self.ac.get_deck_meta(deck.name)
        except AnkiIntegrationDisabledError as e:
            raise DeckOpError(self, str(e)) from e
        except AnkiIntegrationError as e:
            raise DeckOpError(self, str(e))

        deck.meta = DeckMeta(metadata)

        for note_info in notes_info:
            id = note_info['noteId']
            front = note_info['fields']['Front']['value']
            back = note_info['fields']['Back']['value']
            model = note_info['modelName']
            tags = note_info['tags']
            deck.notes.append(Note(id, Field(front), Field(back), model, tags))

        return deck


    def import_deck(self, deck_name: str = None) -> Deck:
        if not deck_name:
            raise DeckOpError(self, "Missing argument: deck_name")

        return self._import_deck(deck_name)