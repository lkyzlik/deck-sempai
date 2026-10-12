from Deck import Deck
from DeckOperator import DeckOpResult
from transformers.Transformer import Transformer


class SkipTransformer(Transformer):
    def transform_deck(self, deck: Deck, **kwargs) -> DeckOpResult:
        self._info(f"Skipping all {len(deck.notes)} notes")
        return DeckOpResult.all_with_status(len(deck.notes), "skipped", op_title="Skipped")
