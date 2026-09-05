from Deck import Deck, Note
from DeckOperator import DeckOpResult, DeckOpError, NoteOpResult
from Enums import Side

from interfaces.Logger import Logger
from tools.TranslateTool import TranslateTool, TranslateToolError
from transformers.Transformer import Transformer


class TranslateTransformer(Transformer):
    def __init__(self, logger: Logger, tool: TranslateTool):
        super().__init__(logger)
        self.tool = tool


    def _transform_note(self, note: Note, side_from: Side, side_to: Side) -> NoteOpResult:
        field_from = note.get_field(side_from)
        field_to = note.get_field(side_to)

        try:
            field_to.text = self.tool.translate(field_from.text)
            field_to.sounds = [] # Clear sounds since the text has changed
        except TranslateToolError as e:
            self._warning(str(e))
            return NoteOpResult(success=False)

        return NoteOpResult(success=True)


    def _transform_deck(self, deck: Deck, side_from: Side, side_to: Side) -> DeckOpResult:
        with self.logger.progress() as prog:
            task = prog.add_task("Translating...", total=len(deck.notes))

            results: list[NoteOpResult] = []
            for note in deck.notes:
                result = self._transform_note(note, side_from, side_to)
                results.append(result)
                prog.update(task, advance=1)

        return DeckOpResult(results, op_title="Translated (AI)")


    def transform_deck(self, deck: Deck, side: str = Side.FRONT + "-" + Side.BACK) -> DeckOpResult:
        try:
            side_from, side_to = side.split("-")
            side_from = Side(side_from)
            side_to = Side(side_to)
        except ValueError:
            raise DeckOpError(self, f"Invalid argument: side, supported format: FROM-TO, where FROM and TO are: {', '.join([s.value for s in Side])}")

        return self._transform_deck(deck, side_from, side_to)
