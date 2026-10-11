import time

import httpx

from pathlib import Path

from Deck import Deck, Field
from Enums import Language, Side
from DeckOperator import NoteOpResult, DeckOpResult, DeckOpError
from ui.Logger import Logger
from integrations.OrdnetIntegration import OrdnetIntegration, OrdnetIntegrationError, OrdnetIntegrationDisabledError
from tools.GrammarTool import GrammarTool, GrammarToolError
from tools.GrammarToolOrdnet import GrammarToolOrdnet
from transformers.Transformer import Transformer


class AddSoundOrdnetTransformer(Transformer):
    def __init__(self, logger: Logger, ordnet: OrdnetIntegration, media_dir: Path):
        super().__init__(logger)
        self.ordnet = ordnet
        self.media_dir = media_dir
        self.grammar = GrammarTool(Language.DANISH)


    def _download_file(self, url: str, output_path: Path) -> None:
        try:
            resp = self.ordnet.client.get(url, timeout=15)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise OrdnetIntegrationError(
                f"Can't reach ordnet.dk to download the sound file. Run 'setup {self.ordnet.name}' to check "
                "the connection and see repair steps."
            )

        if not output_path.parent.exists():
            output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "wb") as f:
            f.write(resp.content)


    def _download_sound(self, word: str, pos: str | None, filename: str) -> Path:
        sound_url = self.ordnet.get_entry(word, pos=GrammarToolOrdnet.POS_KEY_MAP.get(pos))["sound_url"]
        if not sound_url:
            raise OrdnetIntegrationError(f"Can't find sound URL for {word!r}")
        output_path = self.media_dir / filename
        self._download_file(sound_url, output_path)
        return output_path


    def _extract_word(self, text: str) -> str | None:
        word = self.grammar.extract_word(text)["word"]
        return word if word and len(word.split()) == 1 else None


    def _transform_field(self, field: Field, deck_name: str, is_last: bool) -> NoteOpResult:
        if len(field.sounds) > 0:
            self._info(f"{field.get_text_oneline()!r} already has sound, skipped")
            return NoteOpResult(success=False)

        try:
            pos = self.grammar.pos(field.text)
        except GrammarToolError:
            pos = None

        word = self._extract_word(field.text)
        if not word:
            self._warning(f"Can't extract word from {field.get_text_oneline()!r}")
            return NoteOpResult(success=False)

        try:
            sound_path = self._download_sound(word, pos, f"ordnet_{deck_name}_{word}.mp3")
            field.add_sound(sound_path.name)
        except OrdnetIntegrationDisabledError as e:
            raise DeckOpError(self, str(e)) from e
        except OrdnetIntegrationError as e:
            self._warning(f"Can't download sound for {word!r}: {e}")
            if not is_last:
                time.sleep(0.5) # Be polite to the server even on errors
            return NoteOpResult(success=False)

        if not is_last:
            time.sleep(0.5) # Be polite to the server
        return NoteOpResult(success=True)


    def _transform_deck(self, deck: Deck, sides: list[Side]) -> DeckOpResult:
        combined_results = None
        with self.logger.progress() as prog:
            task = prog.add_task(f"Getting sounds", total=len(deck.notes) * len(sides))

            for side_idx, side in enumerate(sides):
                is_last_side = side_idx == len(sides) - 1
                side_results = []
                for note in deck.notes:
                    is_last = is_last_side and note == deck.notes[-1]
                    side_results.append(self._transform_field(note.get_field(side), deck.name, is_last))

                    prog.update(task, advance=1)

                if combined_results is None:
                    combined_results = side_results
                else:
                    combined_results = [NoteOpResult(success=a.success and b.success)
                                        for a, b in zip(combined_results, side_results)]

        return DeckOpResult(combined_results, op_title="Sound added")


    def transform_deck(self, deck: Deck, side: str = None) -> DeckOpResult:
        try:
            sides = Side.parse_list(side)
        except ValueError:
            raise DeckOpError(self, "Invalid argument: side, supported: " +  ", ".join([s.value for s in Side]))

        return self._transform_deck(deck, sides)