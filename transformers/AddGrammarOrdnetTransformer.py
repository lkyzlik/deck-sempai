from pathlib import Path

from Deck import Deck
from DeckOperator import DeckOpResult, DeckOpError
from Enums import Language, Side

from interfaces.Logger import Logger
from integrations.OrdnetIntegration import OrdnetIntegration
from tools.GrammarToolOrdnet import GrammarToolOrdnet
from transformers.AddGrammarTransformer import AddGrammarTransformer
from transformers.Transformer import Transformer


class AddGrammarOrdnetTransformer(Transformer):
    def __init__(self, logger: Logger, ordnet: OrdnetIntegration, media_dir: Path):
        super().__init__(logger)
        self.ordnet = ordnet
        self.media_dir = media_dir


    def transform_deck(self, deck: Deck, side: str = Side.FRONT.value, lang: str = None,
                       grammar_rule: str = None) -> DeckOpResult:
        if not lang:
            raise DeckOpError(self, "Missing argument: lang")
        try:
            lang = Language(lang)
        except ValueError:
            raise DeckOpError(self, "Invalid argument: lang, supported: " +
                                    ', '.join([l.value for l in Language]))

        if lang != Language.DANISH:
            raise DeckOpError(self, f"'ordnet.dk' grammar tool only supports Danish, not {lang!s}")

        tool = GrammarToolOrdnet(lang, self.ordnet, self.media_dir)
        return AddGrammarTransformer(self.logger, tool).transform_deck(deck, side=side, grammar_rule=grammar_rule)
