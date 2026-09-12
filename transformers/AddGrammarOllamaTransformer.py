from pathlib import Path

from Deck import Deck
from DeckOperator import DeckOpResult, DeckOpError
from Enums import Language, Side

from ui.Logger import Logger
from integrations.OllamaIntegration import OllamaIntegration
from tools.GrammarToolOllama import GrammarToolOllama
from transformers.AddGrammarTransformer import AddGrammarTransformer
from transformers.Transformer import Transformer


class AddGrammarOllamaTransformer(Transformer):
    def __init__(self, logger: Logger, ollama: OllamaIntegration, prompts_path: Path = "prompts.toml"):
        super().__init__(logger)
        self.ollama = ollama
        self.prompts_path = prompts_path


    def transform_deck(self, deck: Deck, side: str = Side.FRONT.value, lang: str = None,
                       rule: str = None, model: str = None) -> DeckOpResult:
        if not lang:
            raise DeckOpError(self, "Missing argument: lang")
        try:
            lang = Language(lang)
        except ValueError:
            raise DeckOpError(self, "Invalid argument: lang, supported: " +
                                    ', '.join([l.value for l in Language]))

        tool = GrammarToolOllama(lang, self.ollama, model, self.prompts_path)
        return AddGrammarTransformer(self.logger, tool).transform_deck(deck, side=side, rule=rule)
