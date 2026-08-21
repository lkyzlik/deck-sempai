from pathlib import Path

from Deck import Deck
from DeckOperator import DeckOpResult, DeckOpError
from Enums import Language, Side, GrammarType

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
                        grammar_type: GrammarType, model: str) -> DeckOpResult:
        placeholders = PromptPlaceholders(lang_from=lang)
        try:
            prompt = self.pl.get_prompt(f"grammar.{grammar_type}.{lang.short()}", placeholders)
        except ValueError:
            raise DeckOpError(self, f"Unsupported grammar type: {grammar_type!s}")
        return self.ollama._transform_deck(deck, side, side, prompt, model)


    def transform_deck(self, deck: Deck, side: str = Side.FRONT.value, lang: str = None,
                       grammar_type: str = None, model: str = None) -> DeckOpResult:
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

        if not grammar_type:
            raise DeckOpError(self, "Missing argument: grammar_type, supported: " +
                                    ', '.join([g.value for g in GrammarType]))
        try:
            grammar_type = GrammarType(grammar_type)
        except ValueError:
            raise DeckOpError(self, "Invalid argument: grammar_type, supported: " +
                                    ', '.join([g.value for g in GrammarType]))

        result = self._transform_deck(deck, side, lang, grammar_type, model)
        result.op_title = "Added grammar help (AI)"
        return result


    