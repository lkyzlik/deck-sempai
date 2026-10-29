from pathlib import Path

from deck_sempai.Deck import Deck, Note
from deck_sempai.DeckOperator import DeckOpError, NoteOpResult, DeckOpResult

from deck_sempai.ui.Logger import Logger
from deck_sempai.exporters.StorageExporter import StorageExporter
from deck_sempai.integrations.AnkiIntegration import AnkiIntegration, AnkiIntegrationError, AnkiIntegrationDisabledError


class AnkiExporter(StorageExporter):
    def __init__(self,  logger: Logger, anki: AnkiIntegration, media_dir: Path):
        super().__init__(logger)
        self.anki = anki
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
        for sound, outcome in zip(sounds, self.anki.delete_media_files(sounds)):
            if isinstance(outcome, AnkiIntegrationError):
                self._warning(f"Can't cleanup sound {sound!r}: {outcome}")


    def _store_sounds(self, notes: list[Note], results: list[NoteOpResult]) -> list[list[str]]:
        """Uploads new sounds (those with a temp file) and marks notes with a failed upload as failed.
        Returns the uploaded filenames per note."""
        files = [(i, sound, self.media_dir / sound)
                 for i, note in enumerate(notes)
                 for field in [note.front, note.back]
                 for sound in field.sounds
                 if (self.media_dir / sound).is_file()]  # No temp file means the sound didn't change

        outcomes = self.anki.store_media_files([(sound, path) for _, sound, path in files])

        added_sounds = [[] for _ in notes]
        for (i, sound, path), outcome in zip(files, outcomes):
            if isinstance(outcome, AnkiIntegrationError):
                self._warning(f"Can't add sound {sound!r}: {outcome}")
                results[i] = NoteOpResult("failed")
            else:
                path.unlink(missing_ok=True)  # Remove the temporary file
                added_sounds[i].append(sound)
        return added_sounds


    def _write_notes(self, indices: list[int], payloads: list[dict], write, deck: Deck,
                     results: list[NoteOpResult]):
        for i, outcome in zip(indices, write(payloads)):
            if isinstance(outcome, AnkiIntegrationError):
                self._warning(f"Can't add note {(deck.notes[i].front.get_text_oneline())!r}: {outcome}")
                results[i] = NoteOpResult("failed")


    def remove_notes(self, deck: Deck) -> DeckOpResult:
        try:
            existing_note_ids = set(self.anki.find_notes(f'deck:"{deck.name}"'))
        except AnkiIntegrationDisabledError as e:
            raise DeckOpError(self, str(e)) from e
        except AnkiIntegrationError as e:
            raise DeckOpError(self, str(e))

        # Notes outside the deck are skipped, so a stale id can't remove a note from another deck
        results = [NoteOpResult("skipped") for _ in deck.notes]
        removes = [i for i, note in enumerate(deck.notes) if note.id in existing_note_ids]

        try:
            outcomes = self.anki.delete_notes([deck.notes[i].id for i in removes])
        except AnkiIntegrationDisabledError as e:
            raise DeckOpError(self, str(e)) from e

        for i, outcome in zip(removes, outcomes):
            if isinstance(outcome, AnkiIntegrationError):
                self._warning(f"Can't remove note {(deck.notes[i].front.get_text_oneline())!r}: {outcome}")
                results[i] = NoteOpResult("failed")
            else:
                results[i] = NoteOpResult("ok")

        return DeckOpResult(results, op_title="Removed")


    def remove_deck(self, name: str) -> None:
        try:
            self.anki.delete_deck(name)
        except AnkiIntegrationDisabledError as e:
            raise DeckOpError(self, str(e)) from e
        except AnkiIntegrationError as e:
            raise DeckOpError(self, str(e))


    def get_decks(self) -> list[str]:
        try:
            return self.anki.deck_names()
        except AnkiIntegrationDisabledError as e:
            raise DeckOpError(self, str(e)) from e
        except AnkiIntegrationError as e:
            raise DeckOpError(self, str(e))


    def export_deck(self, deck: Deck) -> DeckOpResult:
        try:
            self.anki.create_deck(deck.name)  # No-op if the deck already exists
            self.anki.save_deck_meta(deck.name, deck.meta.to_dict())
            existing_note_ids = self.anki.find_notes(f'deck:"{deck.name}"')
        except AnkiIntegrationDisabledError as e:
            raise DeckOpError(self, str(e)) from e
        except AnkiIntegrationError as e:
            raise DeckOpError(self, e)

        existing_note_ids = set(existing_note_ids)
        results = [NoteOpResult("ok") for _ in deck.notes]

        try:
            added_sounds = self._store_sounds(deck.notes, results)

            ok = [i for i, result in enumerate(results) if result.status == "ok"]
            updates = [i for i in ok if deck.notes[i].id in existing_note_ids]
            adds = [i for i in ok if deck.notes[i].id not in existing_note_ids]
            self._write_notes(updates, [self._update_note_to_anki(deck.notes[i]) for i in updates],
                              self.anki.update_notes, deck, results)
            self._write_notes(adds, [self._add_note_to_anki(deck.notes[i], deck.name) for i in adds],
                              self.anki.add_notes, deck, results)

            # Sounds of failed notes would be left unused in Anki
            self._cleanup_sounds([sound for i, result in enumerate(results) if result.status == "failed"
                                  for sound in added_sounds[i]])
        except AnkiIntegrationDisabledError as e:
            raise DeckOpError(self, str(e)) from e

        return DeckOpResult(results, op_title="Exported")
