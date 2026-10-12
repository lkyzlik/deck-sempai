
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


    def _resolve_lang(self, deck: Deck, side: Side, lang: str = None) -> Language:
        if not lang:
            lang = deck.meta.lang_front if side == Side.FRONT else deck.meta.lang_back
        try:
            return Language(lang)
        except ValueError:
            raise DeckOpError(self, "Invalid argument: lang, supported: " + ", ".join([l.value for l in Language]))


    def _transformer_for(self, lang: Language) -> Transformer:
        name = self.language_map.get(lang.short()) or self.language_map.get("other", self.DEFAULT_TRANSFORMER)
        transformer = self.transformers.get(name)
        if not transformer:
            raise DeckOpError(self, f"{name!r} transformer not found")
        return transformer


    def transform_deck(self, deck: Deck, side: str = None, lang: str = None) -> DeckOpResult:
        try:
            sides = Side.parse_list(side)
        except ValueError:
            raise DeckOpError(self, "Invalid argument: side, supported: " +  ", ".join([s.value for s in Side]))

        # Group requested sides by resolved language, so each underlying transformer (which
        # itself supports multiple sides) is invoked once per group, with all of that group's
        # sides passed down together, rather than looping one side at a time.
        groups: dict[Language, list[Side]] = {}
        for s in sides:
            resolved_lang = self._resolve_lang(deck, s, lang)
            groups.setdefault(resolved_lang, []).append(s)

        combined_results = None
        op_title = "Skipped"
        for resolved_lang, group_sides in groups.items():
            side_str = ",".join(s.value for s in group_sides)
            if resolved_lang == Language.NONE:
                self._info(f"No language set for side(s) {side_str}, skipping {len(deck.notes)} notes")
                result = DeckOpResult.all_with_status(len(deck.notes), "skipped", op_title="Skipped")
            else:
                result = self._transformer_for(resolved_lang).transform_deck(deck, side=side_str)

            if result.op_title != "Skipped":
                op_title = result.op_title

            if combined_results is None:
                combined_results = result.note_results
            else:
                combined_results = [a + b
                                    for a, b in zip(combined_results, result.note_results)]

        return DeckOpResult(combined_results, op_title=op_title)
