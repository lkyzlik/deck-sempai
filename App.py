import json

from dataclasses import dataclass, asdict
from dacite import from_dict
from platformdirs import user_data_dir
from pathlib import Path
from rich.text import Text

from Config import Config
from Deck import Deck, DeckMeta
from DeckOperator import DeckOpResult, DeckOpError
from Enums import GrammarRule

from exporters.Exporter import Exporter
from exporters.AnkiExporter import AnkiExporter

from importers.Importer import Importer
from importers.AnkiImporter import AnkiImporter
from importers.LineImporter import LineImporter

from integrations.AnkiIntegration import AnkiIntegration
from integrations.Integration import Integration
from integrations.OllamaIntegration import OllamaIntegration
from integrations.OrdnetIntegration import OrdnetIntegration
from ui.RichConsoleFrontend import RichConsoleFrontend

from transformers.Transformer import Transformer
from transformers.AddSoundManager import AddSoundManager
from transformers.AddSoundOrdnetTransformer import AddSoundOrdnetTransformer
from transformers.RemoveSoundTransformer import RemoveSoundTransformer
from transformers.OllamaTransformer import OllamaTransformer
from transformers.TranslateOllamaTransformer import TranslateOllamaTransformer
from transformers.AddGrammarOllamaTransformer import AddGrammarOllamaTransformer
from transformers.AddGrammarOrdnetTransformer import AddGrammarOrdnetTransformer
from transformers.AddGrammarManager import AddGrammarManager
from transformers.TranslateManager import TranslateManager


@dataclass
class AppState:
    current_deck: str = "Default"


class App:
    def __init__(self):
        self.config = Config.load()
        self.state = AppState()

        data_dir = Path(user_data_dir("deck-sempai"))
        self.state_file = data_dir / "state.json"
        self.media_dir = data_dir / "media"

        # Interfaces
        self.frontend = RichConsoleFrontend()

        # Integrations
        self.integrations : dict[str, Integration] = {}
        for name, integration_cls in (("anki", AnkiIntegration), ("ollama", OllamaIntegration), ("ordnet", OrdnetIntegration)):
            integration_config = self.config.integrations.get(name, {})
            integration = integration_cls()
            integration.configure(integration_config)
            integration.enable(integration_config.get("enable", True))
            self.integrations[name] = integration

        self.exporters : dict[str, Exporter] = {
            "anki": AnkiExporter(self.frontend, self.integrations["anki"], self.media_dir),
        }
        self.importers : dict[str, Importer] = {
            "anki": AnkiImporter(self.frontend, self.integrations["anki"]),
            "line": LineImporter(self.frontend),
        }
        self.transformers : dict[str, Transformer] = {
            "add-sound-ordnet": AddSoundOrdnetTransformer(self.frontend, self.integrations["ordnet"], self.media_dir),
            "remove-sound": RemoveSoundTransformer(self.frontend),
            "ollama": OllamaTransformer(self.frontend, self.integrations["ollama"]),
            "translate-ollama": TranslateOllamaTransformer(self.frontend, self.integrations["ollama"]),
            "add-grammar-ollama": AddGrammarOllamaTransformer(self.frontend, self.integrations["ollama"]),
            "add-grammar-ordnet": AddGrammarOrdnetTransformer(self.frontend, self.integrations["ordnet"], self.media_dir),
        }

        # Add managers (this must be done after all individual deck operators are created)
        self.transformers["add-sound"] = AddSoundManager(self.frontend, self.transformers)
        self.transformers["add-grammar"] = AddGrammarManager(self.frontend, self.transformers)
        self.transformers["translate"] = TranslateManager(self.frontend, self.transformers)

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
        return self.importers[self.config.app.deck_storage].import_deck(self.state.current_deck)


    def _save_deck(self, deck: Deck):
        self.exporters[self.config.app.deck_storage].export_deck(deck)


    def _preview(self, title: str, deck: Deck, results: DeckOpResult = None) -> bool:
        self.frontend.print(title)
        self.frontend.show_deck(deck, results, include_metadata=False)
        response = input("Do you want to save changes? (y/n)\n")
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


    def _parse_add_line(self, line: str) -> tuple[str, str, str, str]:
        parts = [part.strip() for part in line.split(";")]
        parts += [""] * (4 - len(parts))
        front, back, model, tags = parts[:4]
        return front or None, back or None, model or None, tags or None


    def _add_notes(self, entries: list[tuple[str, str, str, str]]):
        if not entries:
            return

        try:
            deck: Deck = self._load_deck()

            note_deck = Deck()
            note_deck.meta = deck.meta
            translate_forward = []
            translate_backward = []

            for front, back, model, tags in entries:
                line_kwargs = {"front": front, "back": back or "", "tags": tags}
                if model:
                    line_kwargs["model"] = model
                try:
                    imported: Deck = self.importers["line"].import_deck(**line_kwargs)
                except DeckOpError as e:
                    self.frontend.error(str(e))
                    continue

                note = imported.notes[0]
                note_deck.notes.append(note)
                if not back:
                    translate_forward.append(note)
                elif not front:
                    translate_backward.append(note)

            if not note_deck.notes:
                return

            if translate_forward:
                sub_deck = Deck()
                sub_deck.meta = deck.meta
                sub_deck.notes = translate_forward
                try:
                    self.transformers["translate"].transform_deck(sub_deck, side="front-back")
                except DeckOpError as e:
                    self.frontend.warning(f"{e.operator.__class__.__name__}: {e}")
            if translate_backward:
                sub_deck = Deck()
                sub_deck.meta = deck.meta
                sub_deck.notes = translate_backward
                try:
                    self.transformers["translate"].transform_deck(sub_deck, side="back-front")
                except DeckOpError as e:
                    self.frontend.warning(f"{e.operator.__class__.__name__}: {e}")

            grammar_rule = ",".join(g.value for g in GrammarRule)
            for side in ("front", "back"):
                try:
                    self.transformers["add-sound"].transform_deck(note_deck, side=side)
                except DeckOpError as e:
                    self.frontend.warning(f"{e.operator.__class__.__name__}: {e}")
                try:
                    self.transformers["add-grammar"].transform_deck(note_deck, side=side, grammar_rule=grammar_rule)
                except DeckOpError as e:
                    self.frontend.warning(f"{e.operator.__class__.__name__}: {e}")

            if self._preview("Preview:", note_deck):
                self._save_deck(deck + note_deck)

        except DeckOpError as e:
            self.frontend.error(str(e))
            return

        self._clear_temp_files()


    def add(self, front: str = None, back: str = None, model: str = None, tags: str = None):
        if front or back:
            self._add_notes([(front, back, model, tags)])
            return

        self.frontend.print("Enter notes as 'FRONT; BACK; MODEL; TAGS' (FRONT or BACK required). Enter 'q' after last note.")
        entries = []
        while True:
            line = input("> ").strip()
            if line.lower() == "q":
                break
            if not line:
                continue
            entries.append(self._parse_add_line(line))

        self._add_notes(entries)


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
