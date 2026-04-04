import re

from interfaces.AnkiConnect import AnkiConnect, AnkiConnectError
from Deck import Deck, Note, Card
from importers.Importer import Importer, ImporterError


class AnkiImporter(Importer):
    def __init__(self, ac: AnkiConnect):
        self.name = "anki"
        self.ac = ac


    @staticmethod
    def _anki_to_text(field) -> str:
        field = re.sub(r'<br>', '', field)
        field = re.sub(r'\[sound:[^\]]+\]', '', field)
        return field


    @staticmethod
    def _anki_to_sound(field) -> str:
        match = re.search(r'\[sound:([^\]]+)\]', field)
        return match.group(1) if match else ""
    

    @staticmethod
    def _anki_to_card(field) -> Card:
        text = AnkiImporter._anki_to_text(field)
        sound = AnkiImporter._anki_to_sound(field)
        return Card(text, sound)


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
            front = self._anki_to_card(note_info['fields']['Front']['value'])
            back = self._anki_to_card(note_info['fields']['Back']['value'])
            model = note_info['modelName']
            tags = note_info['tags']
            deck.notes.append(Note(id, front, back, model, tags))

        return deck