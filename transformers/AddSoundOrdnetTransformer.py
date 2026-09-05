import re
import time

import httpx
from bs4 import BeautifulSoup

from pathlib import Path

from Deck import Deck, Field
from Enums import Side
from DeckOperator import NoteOpResult, DeckOpResult, DeckOpError
from interfaces.Logger import Logger
from interfaces.OrdnetIntegration import OrdnetIntegration, OrdnetIntegrationError
from transformers.Transformer import Transformer


class AddSoundOrdnetTransformer(Transformer):
    def __init__(self, logger: Logger, media_dir: Path):
        super().__init__(logger)
        self.ordnet = OrdnetIntegration()
        self.media_dir = media_dir


    def _extract_sound_url(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")

        lydskrift = soup.find("span", class_="lydskrift")
        if not lydskrift:
            raise OrdnetIntegrationError("Can't find sound URL")

        audio = lydskrift.find("audio")
        if not audio:
            raise OrdnetIntegrationError("Can't find sound URL")

        hidden_structure = audio.find("div", class_="hiddenStructure")
        if not hidden_structure:
            raise OrdnetIntegrationError("Can't find sound URL")

        a = hidden_structure.find("a")
        if a and a.get("href", "") and a["href"].endswith(".mp3"):
            return a["href"]
        else:
            raise OrdnetIntegrationError("Can't find sound URL")


    def _download_file(self, url: str, output_path: Path) -> None:
        try:
            resp = self.ordnet.client.get(url, timeout=15)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise OrdnetIntegrationError(f"Can't download file")

        if not output_path.parent.exists():
            output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "wb") as f:
            f.write(resp.content)


    def _download_sound(self, word: str, filename: str) -> Path:
        html = self.ordnet.get_html(word)
        sound_url = self._extract_sound_url(html)
        output_path = self.media_dir / filename
        self._download_file(sound_url, output_path)
        return output_path


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
            sound_path = self._download_sound(word, f"ordnet_{deck_name}_{word}.mp3")
            field.add_sound(sound_path.name)
        except OrdnetIntegrationError as e:
            self._warning(f"Can't download sound for {word!r}")
            if not is_last:
                time.sleep(0.5) # Be polite to the server even on errors
            return NoteOpResult(success=False)

        if not is_last:
            time.sleep(0.5) # Be polite to the server
        return NoteOpResult(success=True)


    def _transform_deck(self, deck: Deck, side: Side) -> DeckOpResult:
        results = []
        with self.logger.progress() as prog:
            task = prog.add_task(f"Getting sounds...", total=len(deck.notes))

            for note in deck.notes:
                is_last = note == deck.notes[-1]
                results.append(self._transform_field(note.get_field(side), deck.name, is_last))

                prog.update(task, advance=1)
            
        return DeckOpResult(results, op_title="Sound added")


    def transform_deck(self, deck: Deck, side: str = Side.BACK) -> DeckOpResult:
        try:
            side = Side(side)
        except ValueError:
            raise DeckOpError(self, "Invalid argument: side, supported: " +  ", ".join([s.value for s in Side]))

        return self._transform_deck(deck, side)