from rich.console import Console
from rich.table import Table
from rich import box
from rich.text import Text
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn

from Deck import Deck, DeckMeta, Field
from DeckOperator import DeckOpResult, DeckOpError

from interfaces.Logger import LoggerProgress


class RichConsoleFrontend:
    COLOR_MAIN_DIM = "#8d6923"
    COLOR_MAIN = "#fae9c8"
    COLOR_SOUND = "#8b0000"

    def __init__(self, console: Console = Console()):
        self.console = console


    def _field_to_rich(self, field: Field):
        text = Text()
        text.append(field.get_text_oneline())
        for sound in field.sounds:
            text.append(Text(" [♪]", style=self.COLOR_SOUND))
        return text


    def print(self, message: str):
        self.console.print(message)


    def info(self, message: str):
        text = Text()
        text.append("Info: ", style="bold blue")
        text.append(message, style="green")
        self.console.print(text)


    def error(self, message: str):
        text = Text()
        text.append("Error: ", style="bold red")
        text.append(message, style="red")
        self.console.print(text)


    def warning(self, message: str):
        text = Text()
        text.append("Warning: ", style="bold yellow")
        text.append(message, style="yellow")
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
            border_style=self.COLOR_MAIN_DIM,
            header_style=self.COLOR_MAIN + " bold",
            row_styles=[self.COLOR_MAIN, self.COLOR_MAIN_DIM],
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
            text.append(f"{key}: ", style=self.COLOR_MAIN_DIM + " bold")
            text.append(str(value), style=self.COLOR_MAIN_DIM)
            self.console.print(text)


    def show_deck_name(self, name: str):
        text = Text()
        text.append("Deck: ", style=self.COLOR_MAIN + " bold")
        text.append(name, style=self.COLOR_MAIN)
        self.console.print(text)
