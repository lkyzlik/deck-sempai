from ollama import chat, ChatResponse, GenerateResponse, ResponseError

from interfaces.Logger import Logger
from interfaces.PromptLoader import PromptLoader, PromptPlaceholders
from transformers.Transformer import Transformer, TransformerError
from Enums import Side
from Deck import Deck, Note
from Results import DeckOpResult, NoteOpResult


class OllamaTransformer(Transformer):
    def __init__(self, logger: Logger, default_model: str = "gemma4", prog_bar_title: str = "Processing..."):
        self.name = "ollama"
        self.logger = logger
        self.default_model = default_model
        self.prog_bar_title = prog_bar_title
        self.pl = PromptLoader("prompts.toml")


    def _warning(self, message: str):
        self.logger.warning(f"{self.name!r} transformer: {message}")


    def _transform_note(self, note: Note, side_from: Side, side_to: Side, prompt: str, model: str) -> NoteOpResult:
        field_from = note.get_field(side_from)
        field_to = note.get_field(side_to)

        try:
            messages = [
                {"role": "user", "content": prompt},
                {"role": "user", "content": field_from.text}
            ]
            response: ChatResponse = chat(model, messages=messages, keep_alive='10s')
            field_to.text = response.message.content.strip()
            field_to.sounds = [] # Clear sounds since the text has changed
        except ResponseError as e:
            self._warning(f"AI edit failed for {field_from.get_text_oneline()!r}")
            return NoteOpResult(success=False)
        
        return NoteOpResult(success=True)


    def _transform_deck(self, deck: Deck, side_from: Side, side_to: Side,
                        prompt: str,  model: str = None) -> DeckOpResult:
        with self.logger.progress() as prog:
            task = prog.add_task(f"{self.prog_bar_title}", total=len(deck.notes))

            results : list[NoteOpResult] = []
            for note in deck.notes:
                result = self._transform_note(note, side_from, side_to, prompt, model or self.default_model)
                results.append(result)
                prog.update(task, advance=1)

        return DeckOpResult(results, op_title="Transformed (AI)")


    def transform_deck(self, deck, side: str = None, prompt: str = None, model: str = None) -> DeckOpResult:
        if not side:
            raise TransformerError(self, "Missing argument: side")
        try:
            side_from, side_to = side.split("-")
            side_from = Side(side_from)
            side_to = Side(side_to)
        except ValueError:
            raise TransformerError(self, f"Invalid argument: side, supported: FROM-TO, where FROM and TO are: {', '.join([s.value for s in Side])}")

        if not prompt:
            raise TransformerError(self, "Missing argument: prompt")
        
        return self._transform_deck(deck, side_from, side_to, prompt, model)