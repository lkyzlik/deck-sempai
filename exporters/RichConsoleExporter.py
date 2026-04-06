import argparse

from rich.console import Console
from rich.table import Table
from rich import box
from rich.text import Text

from Deck import Deck, Field
from exporters.Exporter import Exporter


COLOR_MAIN_DIM = "#8d6923"
COLOR_MAIN = "#fae9c8"
COLOR_SOUND = "#8b0000"


class RichConsoleExporter(Exporter):
    def __init__(self, console: Console):
        self.name = "rich"
        self.console = console


    def _field_to_rich(self, field: Field):
        text = Text()
        text.append(field.get_text_oneline())
        for sound in field.sounds:
            text.append(Text(" [♪]", style=COLOR_SOUND))
        return text

    def _deck_to_rich(self, deck: Deck, max_rows: int = None):
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

        notes = deck.notes if max_rows is None else deck.notes[:max_rows]

        for i, note in enumerate(notes, start=1):
            table.add_row(str(i), self._field_to_rich(note.front), self._field_to_rich(note.back))

        return table


    def export_deck(self, deck: Deck, *args) -> None:
        max_rows = int(args[0]) if 0 < len(args) else None
        self.console.print(self._deck_to_rich(deck, max_rows))