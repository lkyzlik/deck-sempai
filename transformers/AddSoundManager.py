
from Deck import Deck
from DeckOperator import DeckOpError, DeckOpResult, NoteOpResult
from Enums import Language, Side
from ui.Logger import Logger
from transformers.Transformer import Transformer


class AddSoundManager(Transformer):
    """
    Picks which sound-adding transformer to use based on the note's language.
    """
    DEFAULT_TRANSFORMER = "skip"


    def __init__(self, logger: Logger, transformers: dict[str, Transformer], language_map: dict[str, str] = None):
        super().__init__(logger)
        self.transformers = transformers
        self.language_map = language_map or {}


    def _transform_deck(self, deck: Deck, side: Side, lang: Language) -> DeckOpResult:
        if lang == Language.NONE:
            return DeckOpResult.all_ok(len(deck.notes), op_title="Skipped")

        name = self.language_map.get(lang.short()) or self.language_map.get("other", self.DEFAULT_TRANSFORMER)
        transformer = self.transformers.get(name)
        if not transformer:
            raise DeckOpError(self, f"{name!r} transformer not found")

        return transformer.transform_deck(deck, side=side)


    def transform_deck(self, deck: Deck, side: str = None, lang: str = None) -> DeckOpResult:
        if not side:
            return self._transform_deck_all_sides(deck, lang)
        try:
            side = Side(side)
        except ValueError:
            raise DeckOpError(self, f"Invalid argument: side, supported: " +  ", ".join([s.value for s in Side]))

        if not lang:
            lang = deck.meta.lang_front if side == Side.FRONT else deck.meta.lang_back
        try:
            lang = Language(lang)
        except ValueError:
            raise DeckOpError(self, "Invalid argument: lang, supported: " + ", ".join([l.value for l in Language]))

        return self._transform_deck(deck, side, lang)


    def _transform_deck_all_sides(self, deck: Deck, lang: str = None) -> DeckOpResult:
        combined_results = None
        op_title = "Skipped"

        for side in Side:
            result = self.transform_deck(deck, side=side.value, lang=lang)
            if result.op_title != "Skipped":
                op_title = result.op_title

            if combined_results is None:
                combined_results = result.note_results
            else:
                combined_results = [NoteOpResult(success=a.success and b.success)
                                    for a, b in zip(combined_results, result.note_results)]

        return DeckOpResult(combined_results, op_title=op_title)
