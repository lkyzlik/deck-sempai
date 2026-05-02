from pathlib import Path

from Deck import Deck
from DeckOperator import DeckOpResult, DeckOpError
from Enums import Language, Side
from interfaces.Logger import Logger
from interfaces.PromptLoader import PromptLoader, PromptPlaceholders
from transformers.OllamaTransformer import OllamaTransformer
from transformers.Transformer import Transformer


class TranslateOllamaTransformer(Transformer): 
    def __init__(self, logger: Logger,  default_model: str = "gemma4", prompts_path: Path = "prompts.toml"):
        super().__init__(logger)
        self.ollama = OllamaTransformer(logger, default_model, prog_title="Translating...")
        self.pl = PromptLoader(prompts_path)
    

    def _transform_deck(self, deck: Deck, side_from: Side, side_to: Side,
                        lang_from: Language, lang_to: Language, model: str) -> DeckOpResult:
        placeholders = PromptPlaceholders(lang_from=lang_from, lang_to=lang_to)
        prompt = self.pl.get_prompt("translate", placeholders)
        return self.ollama._transform_deck(deck, side_from, side_to, prompt, model)


    def transform_deck(self, deck: Deck, side: str = Side.FRONT + "-" + Side.BACK,
                       lang: str = None, model: str = None) -> DeckOpResult:
        try:
            side_from, side_to = side.split("-")
            side_from = Side(side_from)
            side_to = Side(side_to)
        except ValueError:
            raise DeckOpError(self, f"Invalid argument: side, supported format: FROM-TO, where FROM and TO are: {', '.join([s.value for s in Side])}")
        
        if not lang:
            raise DeckOpError(self, "Missing argument: lang")
        try:
            lang_from, lang_to = lang.split("-")
            lang_from = Language(lang_from)
            lang_to = Language(lang_to)
        except ValueError:
            raise DeckOpError(self, f"Invalid argument: lang, supported format: FROM-TO, where FROM and TO are: {', '.join([l.value for l in Language])}")
        
        result = self._transform_deck(deck, side_from, side_to, lang_from, lang_to, model)
        result.op_title = "Translated (AI)"
        return result
