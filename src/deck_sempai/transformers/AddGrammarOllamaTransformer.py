from pathlib import Path

from deck_sempai.Deck import Deck
from deck_sempai.DeckOperator import DeckOpResult, DeckOpError
from deck_sempai.Enums import Language

from deck_sempai.ui.Logger import Logger
from deck_sempai.integrations.OllamaIntegration import OllamaIntegration
from deck_sempai.tools.grammar.OllamaGrammarTool import OllamaGrammarTool
from deck_sempai.transformers.AddGrammarTransformer import AddGrammarTransformer
from deck_sempai.transformers.Transformer import Transformer


class AddGrammarOllamaTransformer(Transformer):
    def __init__(self, logger: Logger, ollama: OllamaIntegration, prompts_path: Path = None):
        super().__init__(logger)
        self.ollama = ollama
        self.prompts_path = prompts_path


    def transform_deck(self, deck: Deck, side: str = None, lang: str = None,
                       rule: str = None, model: str = None) -> DeckOpResult:
        if not lang:
            raise DeckOpError(self, "Missing argument: lang")
        try:
            lang = Language(lang)
        except ValueError:
            raise DeckOpError(self, "Invalid argument: lang, supported: " +
                                    ', '.join([l.value for l in Language]))

        tool = OllamaGrammarTool(lang, self.ollama, model, self.prompts_path)
        return AddGrammarTransformer(self.logger, tool).transform_deck(deck, side=side, rule=rule)
