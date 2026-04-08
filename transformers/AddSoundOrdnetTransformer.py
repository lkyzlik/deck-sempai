import re
import time

from pathlib import Path

from Deck import Deck, Field
from Results import DeckOpResult, NoteOpResult
from interfaces.Logger import Logger
from interfaces.OrdnetScraper import OrdnetScraper, OrdnetScraperError
from transformers.Transformer import Transformer, TransformerError

from rich.progress import Progress, track


class AddSoundOrdnetTransformer(Transformer):
    def __init__(self, scraper: OrdnetScraper, logger: Logger):
        self.name = "add-sound-ordnet"
        self.scraper = scraper
        self.logger = logger


    def _warning(self, message: str):
        self.logger.warning(f"{self.name!r} transformer: {message}")


    def _extract_word(self, text: str) -> str | None:
        # Remove any text in braces (), [], <>, {}
        text = re.sub(r'[\(\[\{<][^)\]\}>]*[\)\]\}>]', '', text)
        # Remove Danish articles and infinitive markers
        text = re.sub(r'^(en|et|den|det|at)\s+', '', text, flags=re.IGNORECASE)
        # Remove numbers
        text = re.sub(r'\d+', '', text)
        # Remove punctuation
        text = re.sub(r'[^\w\s]', '', text)
        # Remove whitespace around
        text = text.strip()
        # Fail if there is more than one word left
        if len(text.split()) != 1:
            return None
        # Return the cleaned word
        return text.split()[0]


    def _transform_field(self, field: Field, deck_name: str, is_last: bool) -> NoteOpResult:
        if len(field.sounds) > 0:
            self._warning(f"{field.get_text_oneline()!r} already has sound")
            return NoteOpResult(success=False)

        word = self._extract_word(field.text)
        if not word:
            self._warning(f"Can't extract word from {field.get_text_oneline()!r}")
            return NoteOpResult(success=False)

        try:
            sound_path = self.scraper.download_sound(word, f"ordnet_{deck_name}_{word}.mp3")
            field.add_sound(sound_path.name)
        except OrdnetScraperError as e:
            self._warning(f"Can't download sound for {word!r}: {e}")
            if not is_last:
                time.sleep(0.5) # Be polite to the server even on errors
            return NoteOpResult(success=False)

        if not is_last:
            time.sleep(0.5) # Be polite to the server
        return NoteOpResult(success=True)


    # transform add-sound-ordnet [SIDE]
    def transform_deck(self, deck: Deck, *args) -> DeckOpResult:
        try:
            side = args[0] if 0 < len(args) else "back"
            if side not in ("front", "back"):
                raise ValueError()
        except ValueError:
            raise TransformerError(self, f"Invalid argument 1: SIDE, expected 'front' or 'back'")

        results = []
        with self.logger.progress() as prog:
            task = prog.add_task(f"Downloading sounds...", total=len(deck.notes))

            for note in deck.notes:
                is_last = note == deck.notes[-1]
                results.append(self._transform_field(note.get_field(side), deck.name, is_last))

                prog.update(task, advance=1)
            
        return DeckOpResult(results, op_title="Sound added")