from pathlib import Path

from deck_sempai.Deck import Deck
from deck_sempai.DeckOperator import DeckOpResult, DeckOpError
from deck_sempai.Enums import Language, Side

from deck_sempai.ui.Logger import Logger
from deck_sempai.integrations.OllamaIntegration import OllamaIntegration
from deck_sempai.tools.translate.OllamaTranslateTool import OllamaTranslateTool
from deck_sempai.transformers.TranslateTransformer import TranslateTransformer
from deck_sempai.transformers.Transformer import Transformer


class TranslateOllamaTransformer(Transformer):
    def __init__(self, logger: Logger, ollama: OllamaIntegration, prompts_path: Path = None):
        super().__init__(logger)
        self.ollama = ollama
        self.prompts_path = prompts_path


    def transform_deck(self, deck: Deck, side: str = Side.FRONT + ":" + Side.BACK,
                       lang: str = None, model: str = None) -> DeckOpResult:
        if not lang:
            raise DeckOpError(self, "Missing argument: lang")
        try:
            lang_from, lang_to = lang.split(":")
            lang_from = Language(lang_from)
            lang_to = Language(lang_to)
        except ValueError:
            raise DeckOpError(self, f"Invalid argument: lang, supported format: FROM:TO, where FROM and TO are: {', '.join([l.value for l in Language])}")

        tool = OllamaTranslateTool(lang_from, lang_to, self.ollama, model, self.prompts_path)
        return TranslateTransformer(self.logger, tool).transform_deck(deck, side=side)
