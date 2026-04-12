import json
import typer

from dataclasses import dataclass, asdict
from dacite import from_dict
from platformdirs import user_data_dir
from pathlib import Path
from rich.console import Console
from rich.text import Text
from typing import Optional

from Deck import Deck
from Results import DeckOpResult

from exporters.Exporter import Exporter, ExporterError
from exporters.AnkiExporter import AnkiExporter
from exporters.RichConsoleExporter import RichConsoleExporter

from importers.Importer import Importer, ImporterError
from importers.AnkiImporter import AnkiImporter
from importers.LineImporter import LineImporter

from interfaces.AnkiConnect import AnkiConnect
from interfaces.Logger import Logger
from interfaces.OrdnetScraper import OrdnetScraper

from transformers.Transformer import Transformer, TransformerError
from transformers.AddSoundOrdnetTransformer import AddSoundOrdnetTransformer

# TODO: load from .toml file
CONFIG = {
    "load_importer": "anki",
    "save_exporter": "anki",
    "show_exporter": "rich",
}


@dataclass
class AppState:
    current_deck: str = "Default"


class App:
    def __init__(self):
        self.config = CONFIG
        self.state = AppState()

        data_dir = Path(user_data_dir("deck-sempai"))
        self.state_file = data_dir / "state.json"
        self.media_dir = data_dir / "media"

        # Interfaces
        self.logger = Logger()
        ac = AnkiConnect()

        self.exporters : dict[str, Exporter | ShowExporter] = {
            "anki": AnkiExporter(ac, self.logger, self.media_dir),
            "rich": RichConsoleExporter(Console()),
        }
        self.importers : dict[str, Importer] = {
            "anki": AnkiImporter(ac),
            "line": LineImporter(),
        }
        self.transformers : dict[str, Transformer] = {
            "add-sound-ordnet": AddSoundOrdnetTransformer(OrdnetScraper(self.media_dir), self.logger),
        }

        self._load_state()


    def _load_state(self) -> None:
        if not self.state_file.exists():
            self.state = AppState()
            return
    
        with open(self.state_file, "r") as f:
            data = json.load(f)
            self.state = from_dict(AppState, data)


    def _save_state(self) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump(asdict(self.state), f, indent=4)


    def set_deck(self, deck_name: str) -> None:
        self.state.current_deck = deck_name
        self._save_state()


    def load_deck(self):
        return self.importers[self.config["load_importer"]].import_deck(self.state.current_deck)


    def save_deck(self, deck: Deck):
        self.exporters[self.config["save_exporter"]].export_deck(deck)


    def show_deck(self, deck: Deck, results: DeckOpResult = None):
        if results:
            self.exporters[self.config["show_exporter"]].export_deck_with_results(deck, results)
        else:
            self.exporters[self.config["show_exporter"]].export_deck(deck)


    def preview(self, title: str, deck: Deck, results: DeckOpResult = None) -> bool:
        self.logger.print(title)
        self.show_deck(deck, results)
        response = input("Do you want to continue? (y/n)\n")
        return response.lower() == "y"


    def clear_temp_files(self):
        if self.media_dir.exists():
            for file in self.media_dir.glob("*"):
                file.unlink()


CTX_SETTINGS = {"allow_extra_args": True, "ignore_unknown_options": True}

commands = typer.Typer()
app = App()

def parse_kwargs(args: list[str]) -> dict:
    parsed = {}
    for arg in args:
        if "=" in arg:
            key, value = arg.split("=", 1)
            parsed[key] = value
    return parsed


@commands.command()
def deck(name: Optional[str] = typer.Argument(None)):
    """
    Set the current deck to work with. If no NAME is provided, shows the current deck.
    """
    if name:
        app.set_deck(name)
    text = Text()
    text.append("Current deck: ")
    text.append(app.state.current_deck or "(none selected)", style="bold")
    app.logger.print(text)


@commands.command(context_settings=CTX_SETTINGS)
def export(ctx: typer.Context, exporter: str):
    """
    Export the current deck using the specified EXPORTER.
    Additional keyword arguments can be passed to the exporter.
    """
    if exporter not in app.exporters:
        app.logger.error(f"Exporter '{exporter}' not found. Available exporters: {', '.join(app.exporters.keys())}")
        return
    
    try:
        deck = app.load_deck()
        results = app.exporters[exporter].export_deck(deck, **parse_kwargs(ctx.args))
        app.show_deck(deck, results)
    except (ImporterError, ExporterError) as e:
        app.logger.error(str(e))
        return


# 'import' is a reserved keyword in Python, so we use 'import_' instead
@commands.command("import", context_settings=CTX_SETTINGS)
def import_(ctx: typer.Context, importer: str):
    """
    Import a deck using the specified IMPORTER.
    Additional keyword arguments can be passed to the importer.
    """
    if importer not in app.importers:
        app.logger.error(f"Importer '{importer}' not found. Available importers: {', '.join(app.importers.keys())}")
        return

    try:
        imported = app.importers[importer].import_deck(**parse_kwargs(ctx.args))
        if app.preview("Import preview", imported):
            deck = app.load_deck() + imported
            app.save_deck(deck)

    except (ImporterError, ExporterError) as e:
        app.logger.error(str(e))
        return


@commands.command()
def show():
    """
    Show the current deck.
    """
    try:
        deck = app.load_deck()
        app.show_deck(deck)

    except (ImporterError, ExporterError) as e:
        app.logger.error(str(e))
        return


@commands.command(context_settings=CTX_SETTINGS)
def transform(ctx: typer.Context, transformer: str):
    """
    Transform the current deck using the specified TRANSFORMER.
    Additional keyword arguments can be passed to the transformer.
    """
    if transformer not in app.transformers:
        app.logger.error(f"Transformer '{transformer}' not found. Available transformers: {', '.join(app.transformers.keys())}")
        return

    try:
        deck = app.load_deck()
        results = app.transformers[transformer].transform_deck(deck, **parse_kwargs(ctx.args))
        if app.preview("Transform preview", deck, results):
            app.save_deck(deck)

    except (ImporterError, ExporterError, TransformerError) as e:
        app.logger.error(str(e))
        return

    app.clear_temp_files()


if __name__ == "__main__":
    commands()
