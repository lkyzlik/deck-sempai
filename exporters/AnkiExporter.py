from pathlib import Path

from Deck import Deck, Note
from DeckOperator import DeckOpError, NoteOpResult, DeckOpResult

from ui.Logger import Logger
from exporters.StorageExporter import StorageExporter
from integrations.AnkiIntegration import AnkiIntegration, AnkiIntegrationError, AnkiIntegrationDisabledError


class AnkiExporter(StorageExporter):
    def __init__(self,  logger: Logger, ac: AnkiIntegration, media_dir: Path):
        super().__init__(logger)
        self.ac = ac
        self.media_dir = media_dir


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
            except AnkiIntegrationError as e:
                self._warning(f"Can't cleanup sound {sound!r}: {e}")


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
                except AnkiIntegrationDisabledError as e:
                    raise DeckOpError(self, str(e)) from e
                except AnkiIntegrationError as e:
                    self._warning(f"Can't add sound {sound!r}: {e}")
                    self._cleanup_sounds(added_sounds)
                    return NoteOpResult("failed")
                except IOError as e:
                    # No temp file means there has been no change to the sound
                    pass

        # Update texts
        try:
            if note.id in existing_note_ids:
                self.ac.update_note(self._update_note_to_anki(note))
            else:
                self.ac.add_note(self._add_note_to_anki(note, deck_name))
        except AnkiIntegrationDisabledError as e:
            raise DeckOpError(self, str(e)) from e
        except AnkiIntegrationError as e:
            self._warning(f"Can't add note {(note.front.get_text_oneline())!r}: {e}")
            self._cleanup_sounds(added_sounds)
            return NoteOpResult("failed")

        return NoteOpResult("ok")


    def create_deck(self, name: str) -> None:
        try:
            self.ac.create_deck(name)
        except AnkiIntegrationDisabledError as e:
            raise DeckOpError(self, str(e)) from e
        except AnkiIntegrationError as e:
            raise DeckOpError(self, str(e))


    def delete_deck(self, name: str) -> None:
        try:
            self.ac.delete_deck(name)
        except AnkiIntegrationDisabledError as e:
            raise DeckOpError(self, str(e)) from e
        except AnkiIntegrationError as e:
            raise DeckOpError(self, str(e))


    def get_decks(self) -> list[str]:
        try:
            return self.ac.deck_names()
        except AnkiIntegrationDisabledError as e:
            raise DeckOpError(self, str(e)) from e
        except AnkiIntegrationError as e:
            raise DeckOpError(self, str(e))


    def export_deck(self, deck: Deck) -> DeckOpResult:
        try:
            self.ac.save_deck_meta(deck.name, deck.meta.to_dict())
            existing_note_ids = self.ac.find_notes(f'deck:"{deck.name}"')
        except AnkiIntegrationDisabledError as e:
            raise DeckOpError(self, str(e)) from e
        except AnkiIntegrationError as e:
            raise DeckOpError(self, e)

        results = []
        for note in deck.notes:
            result = self._export_note(note, existing_note_ids, deck.name)
            results.append(result)

        return DeckOpResult(results, op_title="Exported")