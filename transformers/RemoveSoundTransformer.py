from Deck import Deck, Field
from Enums import Side
from DeckOperator import NoteOpResult, DeckOpResult, DeckOpError
from transformers.Transformer import Transformer


class RemoveSoundTransformer(Transformer):
    def _transform_field(self, field: Field) -> NoteOpResult:
        if not field.sounds:
            return NoteOpResult(success=False)

        field.sounds = []
        return NoteOpResult(success=True)


    def _transform_deck(self, deck: Deck, side: Side) -> DeckOpResult:
        results = [self._transform_field(note.get_field(side)) for note in deck.notes]
        return DeckOpResult(results, op_title="Sound removed")


    def transform_deck(self, deck: Deck, side: str = Side.BACK) -> DeckOpResult:
        try:
            side = Side(side)
        except ValueError:
            raise DeckOpError(self, "Invalid argument: side, supported: " +  ", ".join([s.value for s in Side]))

        return self._transform_deck(deck, side)
