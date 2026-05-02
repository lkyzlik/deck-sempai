from rich.console import Console
from rich.table import Table
from rich import box
from rich.text import Text

from Deck import Deck, Field
from DeckOperator import DeckOpError, DeckOpResult

from interfaces.Logger import Logger
from interfaces.RichLogger import RichLogger
from exporters.Exporter import ResultsExporter


COLOR_MAIN_DIM = "#8d6923"
COLOR_MAIN = "#fae9c8"
COLOR_SOUND = "#8b0000"


class RichConsoleExporter(ResultsExporter):
    def __init__(self, logger: Logger):
        super().__init__(logger)
        if isinstance(logger, RichLogger):
            self.console = logger.console
        else:
            self.console = Console()


    def _field_to_rich(self, field: Field):
        text = Text()
        text.append(field.get_text_oneline())
        for sound in field.sounds:
            text.append(Text(" [♪]", style=COLOR_SOUND))
        return text


    def _export_deck(self, deck: Deck, result: DeckOpResult = None, max_rows: int = None):
        table = Table(
            show_header=True,
            box=box.DOUBLE_EDGE,
            border_style=COLOR_MAIN_DIM,
            header_style=COLOR_MAIN + " bold",
            row_styles=[COLOR_MAIN, COLOR_MAIN_DIM],
        )
        table.add_column("#")
        table.add_column("☖ Front")
        table.add_column("☗ Back")
        if result:
            table.add_column(result.op_title)

        notes = deck.notes[:max_rows] if max_rows else deck.notes

        for i, note in enumerate(notes):
            row = [
                str(i + 1),
                self._field_to_rich(note.front),
                self._field_to_rich(note.back),
            ]
            if result:
                note_result = result.note_results[i]
                status = "✓" if note_result.success else "✗"
                row.append(Text(status, style="green" if note_result.success else "red"))
            table.add_row(*row)

        self.console.print(table)

        return DeckOpResult.all_ok(len(deck.notes), op_title="Shown")


    def _parse_max_rows(self, max_rows: str) -> int | None:
        if max_rows is None:
            return None
        try:
            max_rows = int(max_rows)
            if max_rows <= 0:
                raise ValueError()
            return max_rows
        except ValueError:
            raise DeckOpError(self, "Invalid argument: max_rows, must be a positive integer")


    def export_deck(self, deck: Deck, max_rows: str = None) -> DeckOpResult:
        return self._export_deck(deck, max_rows=self._parse_max_rows(max_rows))


    def export_deck_with_results(self, deck: Deck, results: DeckOpResult, max_rows: str = None) -> DeckOpResult:
        return self._export_deck(deck, result=results, max_rows=self._parse_max_rows(max_rows))
    