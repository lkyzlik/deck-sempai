from Deck import Deck
from DeckOperator import DeckOpError, DeckOpResult
from Enums import Side, Language
from transformers.Transformer import Transformer
from ui.Logger import Logger


class AddGrammarManager(Transformer):
    """
    Picks which grammar-adding transformer to use based on the note's language.
    """
    DEFAULT_TRANSFORMER = "skip"


    def __init__(self, logger: Logger, transformers: dict[str, Transformer], language_map: dict[str, str] = None):
        super().__init__(logger)
        self.transformers = transformers
        self.language_map = language_map or {}


    def _transform_deck(self, deck: Deck, side: Side, lang: Language, grammar_rule: str) -> DeckOpResult:
        if lang == Language.NONE:
            return DeckOpResult.all_ok(len(deck.notes), op_title="Skipped")

        name = self.language_map.get(lang.short()) or self.language_map.get("other", self.DEFAULT_TRANSFORMER)
        transformer = self.transformers.get(name)
        if not transformer:
            raise DeckOpError(self, f"{name!r} transformer not found")

        return transformer.transform_deck(deck, side=side, lang=lang, grammar_rule=grammar_rule)


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

        return self._transform_deck(deck, side, lang, grammar_rule)
