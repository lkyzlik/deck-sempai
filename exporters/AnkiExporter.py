
from Deck import Deck, Note, Card
from Logger import Logger
from exporters.Exporter import Exporter, ExporterError
from interfaces.AnkiConnect import AnkiConnect, AnkiConnectError


class AnkiExporter(Exporter):
    def __init__(self, ac: AnkiConnect):
        self.name = "anki"
        self.ac = ac
        self.logger = Logger()


    def _card_to_anki(self, card: Card) -> str:
        return card.text + (f'<br><br>[sound:{card.sound}]' if card.sound else "")


    def _add_note_to_anki(self, note: Note, deck_name: str) -> dict:
        return {
            "deckName": deck_name,
            "modelName": note.model,
            "fields": {
                "Front": self._card_to_anki(note.front),
                "Back": self._card_to_anki(note.back),
            },
            "tags": note.tags,
        }


    def _update_note_to_anki(self, note: Note) -> dict:
        return {
            "id": note.id,
            "fields": {
                "Front": self._card_to_anki(note.front),
                "Back": self._card_to_anki(note.back),
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
                self.logger.warning(f"Can't add note {note.front.text!r}: {e}")