import json

from dataclasses import dataclass, asdict
from dacite import from_dict
from platformdirs import user_data_dir
from pathlib import Path
from rich.text import Text

from Deck import Deck, DeckMeta
from DeckOperator import DeckOpResult, DeckOpError

from exporters.Exporter import Exporter
from exporters.AnkiExporter import AnkiExporter

from importers.Importer import Importer
from importers.AnkiImporter import AnkiImporter
from importers.LineImporter import LineImporter

from interfaces.AnkiConnect import AnkiConnect
from interfaces.RichConsoleFrontend import RichConsoleFrontend
from interfaces.OrdnetScraper import OrdnetScraper

from transformers.Transformer import Transformer
from transformers.AddSoundManager import AddSoundManager
from transformers.AddSoundOrdnetTransformer import AddSoundOrdnetTransformer
from transformers.OllamaTransformer import OllamaTransformer
from transformers.TranslateOllamaTransformer import TranslateOllamaTransformer
from transformers.GrammarHelpOllamaTransformer import GrammarHelpOllamaTransformer


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
        self.frontend = RichConsoleFrontend()
        ac = AnkiConnect()

        self.exporters : dict[str, Exporter] = {
            "anki": AnkiExporter(self.frontend, ac, self.media_dir),
        }
        self.importers : dict[str, Importer] = {
            "anki": AnkiImporter(self.frontend, ac),
            "line": LineImporter(self.frontend),
        }
        self.transformers : dict[str, Transformer] = {
            "add-sound-ordnet": AddSoundOrdnetTransformer(self.frontend, OrdnetScraper(self.media_dir)),
            "ollama": OllamaTransformer(self.frontend),
            "translate-ollama": TranslateOllamaTransformer(self.frontend),
            "grammar-help-ollama": GrammarHelpOllamaTransformer(self.frontend),
        }

        # Add managers (this must be done after all individual deck operators are created)
        self.transformers["add-sound"] = AddSoundManager(self.frontend, self.transformers)

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


    def _load_deck(self):
        return self.importers[self.config["load_importer"]].import_deck(self.state.current_deck)


    def _save_deck(self, deck: Deck):
        self.exporters[self.config["save_exporter"]].export_deck(deck)


    def _preview(self, title: str, deck: Deck, results: DeckOpResult = None) -> bool:
        self.frontend.print(title)
        self.frontend.show_deck(deck, results)
        response = input("Do you want to continue? (y/n)\n")
        return response.lower() == "y"


    def _clear_temp_files(self):
        if self.media_dir.exists():
            for file in self.media_dir.glob("*"):
                file.unlink()


    def deck(self, name: str = None):
        if name:
            self._load_state()
            self.state.current_deck = name
            self._save_state()

        self.frontend.show_deck_name(self.state.current_deck)


    def meta(self, **kwargs):
        try:
            deck: Deck = self._load_deck()
            deck.meta.update(kwargs)

            self.frontend.show_deck_name(deck.name)
            self.frontend.show_deck_metadata(deck.meta)

            self._save_deck(deck)
        except DeckOpError as e:
            self.frontend.error(str(e))
            return


    def export(self, exporter: str, **kwargs):
        if exporter not in self.exporters:
            self.frontend.error(f"Exporter '{exporter}' not found. Available exporters: {', '.join(self.exporters.keys())}")
            return

        try:
            deck: Deck = self._load_deck()
            result: DeckOpResult = self.exporters[exporter].export_deck(deck, **kwargs)
            self.frontend.show_deck(deck, result)
        except DeckOpError as e:
            self.frontend.error(str(e))
            return


    def import_(self, importer: str, **kwargs):
        if importer not in self.importers:
            self.frontend.error(f"Importer '{importer}' not found. Available importers: {', '.join(self.importers.keys())}")
            return

        try:
            imported: Deck = self.importers[importer].import_deck(**kwargs)
            if self._preview("Import preview", imported):
                deck: Deck = self._load_deck() + imported
                self._save_deck(deck)

        except DeckOpError as e:
            self.frontend.error(str(e))
            return


    def show(self):
        try:
            deck: Deck = self._load_deck()
            self.frontend.show_deck(deck)

        except DeckOpError as e:
            self.frontend.error(str(e))
            return


    def transform(self, transformer: str, **kwargs):
        if transformer not in self.transformers:
            self.frontend.error(f"Transformer '{transformer}' not found. Available transformers: {', '.join(self.transformers.keys())}")
            return

        try:
            deck: Deck = self._load_deck()
            result: DeckOpResult = self.transformers[transformer].transform_deck(deck, **kwargs)
            if self._preview("Changes preview", deck, result):
                self._save_deck(deck)

        except DeckOpError as e:
            self.frontend.error(str(e))
            return

        self._clear_temp_files()