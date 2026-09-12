from Deck import Deck
from DeckOperator import DeckOpResult
from transformers.Transformer import Transformer


class SkipTransformer(Transformer):
    def transform_deck(self, deck: Deck, **kwargs) -> DeckOpResult:
        return DeckOpResult.all_ok(len(deck.notes), op_title="Skipped")
