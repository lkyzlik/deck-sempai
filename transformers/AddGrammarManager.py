from Deck import Deck
from DeckOperator import DeckOpError, DeckOpResult
from Enums import Side, Language
from transformers.Transformer import Transformer
from interfaces.Logger import Logger


class AddGrammarManager(Transformer):
    """
    Manages which grammar-adding transformer to use for each language and
    handles errors and retries.
    """
    # List of transformers to use for each language in order of preference
    language_map = {
        Language.DANISH: ("add-grammar-ordnet", "add-grammar-ollama"),
    }


    def __init__(self, logger: Logger, transformers: dict[str, Transformer]):
        super().__init__(logger)
        self.transformers = transformers


    def _transform_deck(self, deck: Deck, side: Side, lang: Language, grammar_rule: str) -> DeckOpResult:
        transformer_names = self.language_map.get(lang)
        if not transformer_names:
            raise DeckOpError(self, f"{lang!s} language not supported, supported: {', '.join([str(l) for l in self.language_map.keys()])}")

        for name in transformer_names:
            transformer = self.transformers.get(name)
            if not transformer:
                self._warning(f"{name!r} transformer not found")
                continue

            try:
                return transformer.transform_deck(deck, side=side, lang=lang, grammar_rule=grammar_rule)
            except DeckOpError as e:
                self._warning(str(e))

        raise DeckOpError(self, f"All transformers for {lang!s} language failed")


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

        return self._transform_deck(deck, side, lang, grammar_rule)
