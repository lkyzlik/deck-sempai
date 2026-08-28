from rich.console import Console
from rich.table import Table
from rich import box
from rich.text import Text
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn

from Deck import Deck, DeckMeta, Field
from DeckOperator import DeckOpResult, DeckOpError

from interfaces.Logger import LoggerProgress


class RichConsoleFrontend:
    COLOR_PRIMARY = "#fae9c8"
    COLOR_SECONDARY = "#a8813a"
    COLOR_ACCENT = "#ca3333"
    COLOR_INFO = "blue"
    COLOR_WARNING = "yellow"
    COLOR_ERROR = "red"

    def __init__(self, console: Console = Console()):
        self.console = console


    def _field_to_rich(self, field: Field):
        text = Text()
        text.append(field.get_text_oneline())
        for sound in field.sounds:
            text.append(Text(" [♪]", style=self.COLOR_ACCENT))
        return text


    def print(self, message: str):
        self.console.print(message)


    def info(self, message: str):
        text = Text()
        text.append("Info: ", style="bold " + self.COLOR_INFO)
        text.append(message, style=self.COLOR_INFO)
        self.console.print(text)


    def error(self, message: str):
        text = Text()
        text.append("Error: ", style="bold " + self.COLOR_ERROR)
        text.append(message, style=self.COLOR_ERROR)
        self.console.print(text)


    def warning(self, message: str):
        text = Text()
        text.append("Warning: ", style="bold " + self.COLOR_WARNING)
        text.append(message, style=self.COLOR_WARNING)
        self.console.print(text)


    def progress(self) -> LoggerProgress:
        return Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            console=self.console
        )


    def show_deck(self, deck: Deck, result: DeckOpResult = None,
                  include_metadata: bool = True, max_rows: int = None):
        
        # Validate max_rows
        if max_rows and (max_rows > len(deck.notes) or max_rows < 0):
            self.warning(f"Can't show {max_rows} rows. Showing all notes instead.")
            max_rows = None

        if include_metadata:
            self.show_deck_name(deck.name)
            self.show_deck_metadata(deck.meta)

        table = Table(
            show_header=True,
            box=box.DOUBLE_EDGE,
            border_style=self.COLOR_SECONDARY,
            header_style=self.COLOR_PRIMARY + " bold",
            row_styles=[self.COLOR_PRIMARY, self.COLOR_SECONDARY],
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


    def show_deck_metadata(self, meta: DeckMeta):
        for key, value in meta.to_dict().items():
            text = Text()
            text.append(f"{key}: ", style=self.COLOR_SECONDARY + " bold")
            text.append(str(value), style=self.COLOR_SECONDARY)
            self.console.print(text)


    def show_deck_name(self, name: str):
        text = Text()
        text.append("Deck: ", style=self.COLOR_PRIMARY + " bold")
        text.append(name, style=self.COLOR_PRIMARY)
        self.console.print(text)
