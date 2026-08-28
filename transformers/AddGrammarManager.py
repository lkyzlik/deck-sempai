from Deck import Deck
from DeckOperator import DeckOpError, DeckOpResult
from Enums import Side, Language
from transformers.Transformer import Transformer
from interfaces.Logger import Logger


class AddGrammarManager(Transformer):
    """
    Manages which grammar-adding transformer to use.
    """
    def __init__(self, logger: Logger, transformers: dict[str, Transformer]):
        super().__init__(logger)
        self.transformers = transformers


    def transform_deck(self, deck: Deck, side: str = None, lang: str = None,
                       grammar_rule: str = None) -> DeckOpResult:
        if not side:
            raise DeckOpError(self, "Missing argument: side")
        try:
            side = Side(side)
        except ValueError:
            raise DeckOpError(self, "Invalid argument: side, supported: " + ", ".join([s.value for s in Side]))

        if not lang:
            lang = deck.meta.lang_front if side == Side.FRONT else deck.meta.lang_back
        try:
            lang = Language(lang)
        except ValueError:
            raise DeckOpError(self, "Invalid argument: lang, supported: " + ", ".join([l.value for l in Language]))

        if lang == Language.NONE:
            raise DeckOpError(self, "Missing argument: lang, and no language found in deck metadata")

        # For now, always default to the AddGrammarOllamaTransformer
        return self.transformers['add-grammar-ollama'].transform_deck(deck, side=side, lang=lang, grammar_rule=grammar_rule)
