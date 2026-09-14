from pathlib import Path

from Deck import Deck
from DeckOperator import DeckOpResult, DeckOpError
from Enums import Language, Side

from ui.Logger import Logger
from integrations.OllamaIntegration import OllamaIntegration
from tools.TranslateToolOllama import TranslateToolOllama
from transformers.TranslateTransformer import TranslateTransformer
from transformers.Transformer import Transformer


class TranslateOllamaTransformer(Transformer):
    def __init__(self, logger: Logger, ollama: OllamaIntegration, prompts_path: Path = "prompts.toml"):
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

        tool = TranslateToolOllama(lang_from, lang_to, self.ollama, model, self.prompts_path)
        return TranslateTransformer(self.logger, tool).transform_deck(deck, side=side)
