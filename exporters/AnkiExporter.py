
from Deck import Deck, Note
from interfaces.Logger import Logger
from exporters.Exporter import Exporter, ExporterError
from interfaces.AnkiConnect import AnkiConnect, AnkiConnectError


class AnkiExporter(Exporter):
    def __init__(self, ac: AnkiConnect, logger: Logger):
        self.name = "anki"
        self.ac = ac
        self.logger = logger


    def _add_note_to_anki(self, note: Note, deck_name: str) -> dict:
        return {
            "deckName": deck_name,
            "modelName": note.model,
            "fields": {
                "Front": str(note.front),
                "Back": str(note.back),
            },
            "tags": note.tags,
        }


    def _update_note_to_anki(self, note: Note) -> dict:
        return {
            "id": note.id,
            "fields": {
                "Front": str(note.front),
                "Back": str(note.back),
            },
            "tags": note.tags,
        }


    def export_deck(self, deck: Deck, *args) -> None:
        try:
            existing_note_ids = self.ac.find_notes(f'deck:{deck.name}')
        except AnkiConnectError as e:
            raise ExporterError(self, e)
        
        for note in deck.notes:
            try:
                if note.id in existing_note_ids:
                    self.ac.update_note(self._update_note_to_anki(note))
                else:
                    self.ac.add_note(self._add_note_to_anki(note, deck.name))
            except AnkiConnectError as e:
                self.logger.warning(f"Can't add note {(note.front.get_text_oneline())!r}: {e}")