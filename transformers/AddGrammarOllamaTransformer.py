from pathlib import Path

from Deck import Deck
from DeckOperator import DeckOpResult, DeckOpError
from Enums import Language, Side

from interfaces.Logger import Logger
from interfaces.PromptLoader import PromptLoader, PromptPlaceholders
from transformers.OllamaTransformer import OllamaTransformer
from transformers.Transformer import Transformer


class AddGrammarOllamaTransformer(Transformer):
    def __init__(self, logger: Logger,  default_model: str = "gemma4", prompts_path: Path = "prompts.toml"):
        super().__init__(logger)
        self.ollama = OllamaTransformer(logger, default_model, prog_title="Adding grammar help...")
        self.pl = PromptLoader(prompts_path)

    
    def _transform_deck(self, deck: Deck, side: Side, lang: Language,
                        help_type: str, model: str) -> DeckOpResult:
        placeholders = PromptPlaceholders(lang_from=lang)
        prompt = self.pl.get_prompt(f"grammar.{help_type}.{lang.short()}", placeholders)
        return self.ollama._transform_deck(deck, side, side, prompt, model)
    

    def transform_deck(self, deck: Deck, side: str = Side.FRONT.value, lang: str = None,
                       help_type: str = None, model: str = None) -> DeckOpResult:
        try:
            side = Side(side)
        except ValueError:
            raise DeckOpError(self, "Invalid argument: side, supported: " +
                                    ', '.join([s.value for s in Side]))
        
        if not lang:
            raise DeckOpError(self, "Missing argument: lang")
        try:
            lang = Language(lang)
        except ValueError:
            raise DeckOpError(self, "Invalid argument: lang, supported: " +
                                    ', '.join([l.value for l in Language]))
        
        if not help_type:
            raise DeckOpError(self, "Missing argument: help_type, supported: " +
                                    ', '.join(self.pl.get_subkeys('grammar', include_leafs=False)))
        

        result = self._transform_deck(deck, side, lang, help_type, model)
        result.op_title = "Added grammar help (AI)"
        return result


    