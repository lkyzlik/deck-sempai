
from Enums import Language
from interfaces.Logger import Logger
from transformers.Transformer import Transformer, TransformerError, DeckOpResult


class AddSoundManager(Transformer):
    """
    Manages which sound-adding transformer to use for each language and
    handles errors and retries.
    """
    # List of transformers to use for each language in order of preference
    language_map = {
        Language.DANISH: ("add-sound-ordnet",),
    }


    def __init__(self, logger: Logger, transformers: dict[str, Transformer]):
        self.name = "add-sound"
        self.logger = logger
        self.transformers = transformers


    def _warning(self, message: str):
        self.logger.warning(f"{self.name!r} transformer: {message}")


    def transform_deck(self, deck, side: str, lang: str) -> DeckOpResult:
        try:
            lang = Language(lang)
        except ValueError:
            raise TransformerError(self, f"Unknown language {lang!r}, supported: {', '.join(self.language_map.keys())}")

        transformer_names = self.language_map.get(lang)
        if not transformer_names:
            raise TransformerError(self, f"Unsupported language {lang!r}, supported: {', '.join(self.language_map.keys())}")  

        for name in transformer_names:
            transformer = self.transformers.get(name)
            if not transformer:
                self._warning(f"{name!r} transformer not found")
                continue

            try:
                return transformer.transform_deck(deck, side=side)
            except TransformerError as e:
                self._warning(str(e))

        raise TransformerError(self, f"All transformers for language {lang!r} failed")