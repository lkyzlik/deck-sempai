from Deck import Deck
from DeckOperator import DeckOpError, DeckOpResult
from Enums import Side, Language
from transformers.Transformer import Transformer
from ui.Logger import Logger


class TranslateManager(Transformer):
    """
    Manages which translation transformer to use.
    """
    def __init__(self, logger: Logger, transformers: dict[str, Transformer]):
        super().__init__(logger)
        self.transformers = transformers


    def transform_deck(self, deck: Deck, side: str = Side.FRONT + "-" + Side.BACK,
                       lang: str = None) -> DeckOpResult:
        try:
            side_from, side_to = side.split("-")
            side_from = Side(side_from)
            side_to = Side(side_to)
        except ValueError:
            raise DeckOpError(self, f"Invalid argument: side, supported format: FROM-TO, where FROM and TO are: {', '.join([s.value for s in Side])}")

        if not lang:
            lang_from = deck.meta.lang_front if side_from == Side.FRONT else deck.meta.lang_back
            lang_to = deck.meta.lang_front if side_to == Side.FRONT else deck.meta.lang_back
        else:
            try:
                lang_from, lang_to = lang.split("-")
            except ValueError:
                raise DeckOpError(self, f"Invalid argument: lang, supported format: FROM-TO, where FROM and TO are: {', '.join([l.value for l in Language])}")

        try:
            lang_from = Language(lang_from)
            lang_to = Language(lang_to)
        except ValueError:
            raise DeckOpError(self, f"Invalid argument: lang, supported format: FROM-TO, where FROM and TO are: {', '.join([l.value for l in Language])}")

        if lang_from == Language.NONE or lang_to == Language.NONE:
            raise DeckOpError(self, "Missing argument: lang, and no language found in deck metadata")

        # For now, always default to the TranslateOllamaTransformer
        return self.transformers['translate-ollama'].transform_deck(deck, side=f"{side_from}-{side_to}", lang=f"{lang_from}-{lang_to}")
