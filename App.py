import json

from dataclasses import dataclass, asdict
from dacite import from_dict
from platformdirs import user_data_dir
from pathlib import Path
from rich.console import Console
from rich.text import Text

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
from transformers.AddSoundManager import AddSoundManager
from transformers.AddSoundOrdnetTransformer import AddSoundOrdnetTransformer


@dataclass
class AppState:
    current_deck: str = "Default"


class App:
    def __init__(self, config: dict):
        self.config = config
        self.state = AppState()

        data_dir = Path(user_data_dir("deck-sempai"))
        self.state_file = data_dir / "state.json"
        self.media_dir = data_dir / "media"

        # Interfaces
        self.logger = Logger()
        ac = AnkiConnect()

        self.exporters : dict[str, Exporter] = {
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

        # Add managers (this must be done after all individual transformers are created)
        self.transformers["add-sound"] = AddSoundManager(self.logger, self.transformers)

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


    def _set_deck(self, deck_name: str) -> None:
        self.state.current_deck = deck_name
        self._save_state()


    def _load_deck(self):
        return self.importers[self.config["load_importer"]].import_deck(self.state.current_deck)


    def _save_deck(self, deck: Deck):
        self.exporters[self.config["save_exporter"]].export_deck(deck)


    def _show_deck(self, deck: Deck, results: DeckOpResult = None):
        if results:
            self.exporters[self.config["show_exporter"]].export_deck_with_results(deck, results)
        else:
            self.exporters[self.config["show_exporter"]].export_deck(deck)


    def _preview(self, title: str, deck: Deck, results: DeckOpResult = None) -> bool:
        self.logger.print(title)
        self._show_deck(deck, results)
        response = input("Do you want to continue? (y/n)\n")
        return response.lower() == "y"


    def _clear_temp_files(self):
        if self.media_dir.exists():
            for file in self.media_dir.glob("*"):
                file.unlink()


    def deck(self, name: str = None):
        if name:
            self._set_deck(name)
        text = Text()
        text.append("Current deck: ")
        text.append(self.state.current_deck or "(none selected)", style="bold")
        self.logger.print(text)


    def export(self, exporter: str, **kwargs):
        if exporter not in self.exporters:
            self.logger.error(f"Exporter '{exporter}' not found. Available exporters: {', '.join(self.exporters.keys())}")
            return

        try:
            deck = self._load_deck()
            results = self.exporters[exporter].export_deck(deck, **kwargs)
            self._show_deck(deck, results)
        except (ImporterError, ExporterError) as e:
            self.logger.error(str(e))
            return


    def import_(self, importer: str, **kwargs):
        if importer not in self.importers:
            self.logger.error(f"Importer '{importer}' not found. Available importers: {', '.join(self.importers.keys())}")
            return

        try:
            imported = self.importers[importer].import_deck(**kwargs)
            if self._preview("Import preview", imported):
                deck = self._load_deck() + imported
                self._save_deck(deck)

        except (ImporterError, ExporterError) as e:
            self.logger.error(str(e))
            return


    def show(self):
        try:
            deck = self._load_deck()
            self._show_deck(deck)

        except (ImporterError, ExporterError) as e:
            self.logger.error(str(e))
            return


    def transform(self, transformer: str, **kwargs):
        if transformer not in self.transformers:
            self.logger.error(f"Transformer '{transformer}' not found. Available transformers: {', '.join(self.transformers.keys())}")
            return

        try:
            deck = self._load_deck()
            results = self.transformers[transformer].transform_deck(deck, **kwargs)
            if self._preview("Changes preview", deck, results):
                self._save_deck(deck)

        except (ImporterError, ExporterError, TransformerError) as e:
            self.logger.error(str(e))
            return

        self._clear_temp_files()