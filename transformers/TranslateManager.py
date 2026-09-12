from Deck import Deck
from DeckOperator import DeckOpError, DeckOpResult, NoteOpResult
from Enums import Side, Language
from transformers.Transformer import Transformer
from ui.Logger import Logger


class TranslateManager(Transformer):
    """
    Picks which translation transformer to use based on the from/to language pair.
    """
    DEFAULT_TRANSFORMER = "skip"


    def __init__(self, logger: Logger, transformers: dict[str, Transformer], language_pair_map: dict[str, str] = None):
        super().__init__(logger)
        self.transformers = transformers
        self.language_pair_map = language_pair_map or {}


    def transform_deck(self, deck: Deck, side: str = None, lang: str = None) -> DeckOpResult:
        if side is None:
            return self._transform_deck_auto(deck, lang)

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

        pair = f"{lang_from.short()}-{lang_to.short()}"
        name = self.language_pair_map.get(pair) or self.language_pair_map.get("other", self.DEFAULT_TRANSFORMER)
        transformer = self.transformers.get(name)
        if not transformer:
            raise DeckOpError(self, f"{name!r} transformer not found")

        return transformer.transform_deck(deck, side=f"{side_from}-{side_to}", lang=f"{lang_from}-{lang_to}")


    def _transform_deck_auto(self, deck: Deck, lang: str = None) -> DeckOpResult:
        """
        Translates each note from its filled side to its empty side, skipping notes
        that already have text on both sides.
        """
        forward_indices = []
        backward_indices = []

        for i, note in enumerate(deck.notes):
            has_front = bool(note.front.text)
            has_back = bool(note.back.text)
            if has_front and not has_back:
                forward_indices.append(i)
            elif has_back and not has_front:
                backward_indices.append(i)

        results = [NoteOpResult(success=True) for _ in deck.notes]

        for indices, side in ((forward_indices, f"{Side.FRONT}-{Side.BACK}"), (backward_indices, f"{Side.BACK}-{Side.FRONT}")):
            if not indices:
                continue

            sub_deck = Deck()
            sub_deck.meta = deck.meta
            sub_deck.notes = [deck.notes[i] for i in indices]

            sub_result = self.transform_deck(sub_deck, side=side, lang=lang)
            for i, note_result in zip(indices, sub_result.note_results):
                results[i] = note_result

        return DeckOpResult(results, op_title="Translated (AI)")
