import argparse

from rich.console import Console
from rich.table import Table
from rich import box
from rich.text import Text

from Deck import Deck, Note, Card
from exporters.Exporter import Exporter


COLOR_MAIN_DIM = "#8d6923"
COLOR_MAIN = "#fae9c8"
COLOR_SOUND = "#8b0000"


class RichConsoleExporter(Exporter):
    def __init__(self):
        self.name = "rich"
        self.console = Console()


    def _card_to_rich(self, card: Card):
        return Text(card.text) + (Text(" [♪]", style=COLOR_SOUND) if card.sound else "")


    def _deck_to_rich(self, deck: Deck, max_rows: int = None):
        table = Table(
            show_header=True,
            box=box.DOUBLE_EDGE,
            border_style=COLOR_MAIN_DIM,
            header_style=COLOR_MAIN + " bold",
            row_styles=[COLOR_MAIN, COLOR_MAIN_DIM],
        )
        table.add_column("☖ Front")
        table.add_column("☗ Back")

        notes = deck.notes if max_rows is None else deck.notes[:max_rows]

        for note in notes:
            table.add_row(self._card_to_rich(note.front), self._card_to_rich(note.back))

        return table


    def export_deck(self, deck: Deck, *args) -> None:
        max_rows = int(args[0]) if 0 < len(args) else None
        self.console.print(self._deck_to_rich(deck, max_rows))