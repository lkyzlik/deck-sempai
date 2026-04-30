from pathlib import Path

from Deck import Deck, Note
from Results import DeckOpResult, NoteOpResult
from interfaces.Logger import Logger
from exporters.Exporter import Exporter, ExporterError
from interfaces.AnkiConnect import AnkiConnect, AnkiConnectError


class AnkiExporter(Exporter):
    def __init__(self, ac: AnkiConnect, logger: Logger, media_dir: Path):
        self.name = "anki"
        self.ac = ac
        self.logger = logger
        self.media_dir = media_dir


    def _warning(self, message: str):
        self.logger.warning(f'{self.name!r} exporter: {message}')


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


    def _cleanup_sounds(self, sounds: list[str]):
        for sound in sounds:
            try:
                self.ac.delete_media_file(sound)
            except AnkiConnectError as e:
                self._warning(f"Can't cleanup sound {sound!r}")


    def _export_note(self, note: Note, existing_note_ids: list[int], deck_name: str) -> NoteOpResult:
        # Update media
        added_sounds = []

        for field in [note.front, note.back]:
            for sound in field.sounds:
                sound_file = self.media_dir / sound
                try:
                    self.ac.store_media_file(sound, sound_file)
                    sound_file.unlink(missing_ok=True)  # Remove the temporary file
                    added_sounds.append(sound)
                except AnkiConnectError as e:
                    self._warning(f"Can't add sound {sound!r}")
                    self._cleanup_sounds(added_sounds)
                    return NoteOpResult(False)
                except IOError as e:
                    # No temp file means there has been no change to the sound
                    pass

        # Update texts
        try:
            if note.id in existing_note_ids:
                self.ac.update_note(self._update_note_to_anki(note))
            else:
                self.ac.add_note(self._add_note_to_anki(note, deck_name))
        except AnkiConnectError as e:
            self._warning(f"Can't add note {(note.front.get_text_oneline())!r}")
            self._cleanup_sounds(added_sounds)
            return NoteOpResult(False)

        return NoteOpResult(True)


    def export_deck(self, deck: Deck) -> DeckOpResult:
        try:
            existing_note_ids = self.ac.find_notes(f'deck:{deck.name}')
        except AnkiConnectError as e:
            raise ExporterError(self, e)

        results = []
        for note in deck.notes:
            result = self._export_note(note, existing_note_ids, deck.name)
            results.append(result)

        return DeckOpResult(results, op_title="Exported")