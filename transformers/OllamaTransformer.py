from interfaces.Logger import Logger
from interfaces.OllamaIntegration import OllamaIntegration, OllamaIntegrationError, OllamaIntegrationDisabledError
from transformers.Transformer import Transformer
from Enums import Side
from Deck import Deck, Note
from DeckOperator import NoteOpResult, DeckOpResult, DeckOpError


class OllamaTransformer(Transformer):
    def __init__(self, logger: Logger, default_model: str = "gemma4", prog_title: str = "Processing..."):
        super().__init__(logger)
        self.default_model = default_model
        self.prog_title = prog_title
        self.ollama = OllamaIntegration()


    def _transform_note(self, note: Note, side_from: Side, side_to: Side, prompt: str, think: bool | str,
                        model: str, temperature: float = None) -> NoteOpResult:
        field_from = note.get_field(side_from)
        field_to = note.get_field(side_to)

        messages = [
            {"role": "user", "content": prompt},
            {"role": "user", "content": field_from.text}
        ]
        try:
            field_to.text = self.ollama.chat(model, messages, think=think, temperature=temperature)
            field_to.sounds = [] # Clear sounds since the text has changed
        except OllamaIntegrationDisabledError as e:
            raise DeckOpError(self, str(e)) from e
        except OllamaIntegrationError as e:
            self._warning(f"AI edit failed for {field_from.get_text_oneline()!r}")
            return NoteOpResult(success=False)

        return NoteOpResult(success=True)


    def _transform_deck(self, deck: Deck, side_from: Side, side_to: Side, prompt: str, think: str | bool,
                        model: str = None, temperature: float = None) -> DeckOpResult:
        with self.logger.progress() as prog:
            task = prog.add_task(f"{self.prog_title}", total=len(deck.notes))

            results : list[NoteOpResult] = []
            for note in deck.notes:
                result = self._transform_note(note, side_from, side_to, prompt, think,
                                              model or self.default_model, temperature)
                results.append(result)
                prog.update(task, advance=1)

        return DeckOpResult(results, op_title="Transformed (AI)")


    def transform_deck(self, deck, side: str = None, prompt: str = None, model: str = None,
                       think: str = None, temperature: str = None) -> DeckOpResult:
        if not side:
            raise DeckOpError(self, "Missing argument: side")
        try:
            side_from, side_to = side.split("-")
            side_from = Side(side_from)
            side_to = Side(side_to)
        except ValueError:
            raise DeckOpError(self, f"Invalid argument: side, supported: FROM-TO, where FROM and TO are: {', '.join([s.value for s in Side])}")

        if not prompt:
            raise DeckOpError(self, "Missing argument: prompt")

        if think is None:
            think = False
        elif think not in ["low", "medium", "high"]:
            think = bool(think)

        if temperature is not None:
            try:
                temperature = float(temperature)
            except ValueError:
                raise DeckOpError(self, "Invalid argument: temperature, must be a number")

        return self._transform_deck(deck, side_from, side_to, prompt, think, model, temperature)