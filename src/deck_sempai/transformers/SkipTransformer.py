from deck_sempai.Deck import Deck
from deck_sempai.DeckOperator import DeckOpResult
from deck_sempai.transformers.Transformer import Transformer


class SkipTransformer(Transformer):
    def transform_deck(self, deck: Deck, **kwargs) -> DeckOpResult:
        self._info(f"Skipping all {len(deck.notes)} notes")
        return DeckOpResult.all_with_status(len(deck.notes), "skipped", op_title="Skipped")
