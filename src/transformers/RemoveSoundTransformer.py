from Deck import Deck, Field
from Enums import Side
from DeckOperator import NoteOpResult, DeckOpResult, DeckOpError
from transformers.Transformer import Transformer


class RemoveSoundTransformer(Transformer):
    def _transform_field(self, field: Field) -> NoteOpResult:
        if not field.sounds:
            self._info(f"{field.get_text_oneline()!r} has no sound, skipped")
            return NoteOpResult("skipped")

        field.sounds = []
        return NoteOpResult("ok")


    def _transform_deck(self, deck: Deck, side: Side) -> DeckOpResult:
        results = [self._transform_field(note.get_field(side)) for note in deck.notes]
        return DeckOpResult(results, op_title="Sound removed")


    def transform_deck(self, deck: Deck, side: str = None) -> DeckOpResult:
        try:
            sides = Side.parse_list(side)
        except ValueError:
            raise DeckOpError(self, "Invalid argument: side, supported: " +  ", ".join([s.value for s in Side]))

        combined_results = None
        for s in sides:
            result = self._transform_deck(deck, s)
            if combined_results is None:
                combined_results = result.note_results
            else:
                combined_results = [a + b
                                    for a, b in zip(combined_results, result.note_results)]

        return DeckOpResult(combined_results, op_title="Sound removed")
