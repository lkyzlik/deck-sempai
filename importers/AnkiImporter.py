import re

from interfaces.AnkiConnect import AnkiConnect, AnkiConnectError
from Deck import Deck, Field, Note
from importers.Importer import Importer, ImporterError


class AnkiImporter(Importer):
    def __init__(self, ac: AnkiConnect):
        self.name = "anki"
        self.ac = ac

    # import anki DECK_NAME
    def import_deck(self, *args) -> Deck:
        deck_name = args[0] if 0 < len(args) else None
        if not deck_name:
            raise ImporterError(self, "Missing argument 1: DECK_NAME")

        deck = Deck(deck_name)

        try:
            note_ids = self.ac.find_notes(f'deck:{deck.name}')
            notes_info = self.ac.notes_info(note_ids)
        except AnkiConnectError as e:
            raise ImporterError(self, str(e))
        
        for note_info in notes_info:
            id = note_info['noteId']
            front = note_info['fields']['Front']['value']
            back = note_info['fields']['Back']['value']
            model = note_info['modelName']
            tags = note_info['tags']
            deck.notes.append(Note(id, Field(front), Field(back), model, tags))

        return deck