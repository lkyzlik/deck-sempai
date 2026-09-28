import json
import tomllib

from dataclasses import dataclass, asdict
from dacite import from_dict
from platformdirs import user_data_dir
from pathlib import Path
from rich.text import Text

from Config import Config
from Deck import Deck, DeckMeta
from DeckOperator import DeckOpResult, DeckOpError
from Enums import GrammarRule, Language

from exporters.Exporter import Exporter
from exporters.StorageExporter import StorageExporter
from exporters.AnkiExporter import AnkiExporter

from importers.Importer import Importer
from importers.AnkiImporter import AnkiImporter
from importers.LineImporter import LineImporter

from integrations.AnkiIntegration import AnkiIntegration
from integrations.Integration import Integration
from integrations.OllamaIntegration import OllamaIntegration
from integrations.OrdnetIntegration import OrdnetIntegration
from ui.Frontend import Frontend, InteractiveAbort
from ui.RichConsoleFrontend import RichConsoleFrontend
from ui.SimpleConsoleFrontend import SimpleConsoleFrontend

from transformers.Transformer import Transformer
from transformers.AddSoundManager import AddSoundManager
from transformers.AddSoundOrdnetTransformer import AddSoundOrdnetTransformer
from transformers.RemoveSoundTransformer import RemoveSoundTransformer
from transformers.OllamaTransformer import OllamaTransformer
from transformers.TranslateOllamaTransformer import TranslateOllamaTransformer
from transformers.AddGrammarOllamaTransformer import AddGrammarOllamaTransformer
from transformers.AddGrammarOrdnetTransformer import AddGrammarOrdnetTransformer
from transformers.AddGrammarManager import AddGrammarManager
from transformers.SkipTransformer import SkipTransformer
from transformers.TranslateManager import TranslateManager


@dataclass
class AppState:
    current_deck: str = "Default"


class App:
    _CREATE_NEW_DECK_OPTION = "Create new"
    _CURRENT_DECK_SUFFIX = " (current)"

    def __init__(self):
        self.config = Config.load()
        self.state = AppState()

        with open(Path(__file__).parent / "pyproject.toml", "rb") as f:
            self.version = tomllib.load(f)["project"]["version"]

        data_dir = Path(user_data_dir("deck-sempai"))
        self.state_file = data_dir / "state.json"
        self.media_dir = data_dir / "media"

        frontends: dict[str, type[Frontend]] = {
            "rich": RichConsoleFrontend,
            "simple": SimpleConsoleFrontend,
        }
        frontend_cls = frontends.get(self.config.app.frontend)
        if not frontend_cls:
            raise ValueError(f"Frontend '{self.config.app.frontend}' not found. Available frontends: {', '.join(frontends)}")
        self.frontend = frontend_cls()

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
            "skip": SkipTransformer(self.frontend),
            "add-sound-ordnet": AddSoundOrdnetTransformer(self.frontend, self.integrations["ordnet"], self.media_dir),
            "remove-sound": RemoveSoundTransformer(self.frontend),
            "ollama": OllamaTransformer(self.frontend, self.integrations["ollama"]),
            "translate-ollama": TranslateOllamaTransformer(self.frontend, self.integrations["ollama"]),
            "add-grammar-ollama": AddGrammarOllamaTransformer(self.frontend, self.integrations["ollama"]),
            "add-grammar-ordnet": AddGrammarOrdnetTransformer(self.frontend, self.integrations["ordnet"], self.media_dir),
        }

        # Add managers (this must be done after all individual deck operators are created)
        self.transformers["add-sound"] = AddSoundManager(self.frontend, self.transformers, self.config.commands.sound)
        self.transformers["add-grammar"] = AddGrammarManager(self.frontend, self.transformers, self.config.commands.grammar)
        self.transformers["translate"] = TranslateManager(self.frontend, self.transformers, self.config.commands.translate)

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


    def _clear_temp_files(self):
        if self.media_dir.exists():
            for file in self.media_dir.glob("*"):
                file.unlink()


    def _pick_deck(self, exporter: StorageExporter, prompt: str, extra_options: list[str] = ()) -> str | None:
        try:
            names = sorted(exporter.get_decks())
        except DeckOpError as e:
            self.frontend.error(str(e))
            return None

        options = [n + (self._CURRENT_DECK_SUFFIX if n == self.state.current_deck else "") for n in names]
        options += list(extra_options)

        choice = self.frontend.choice(prompt, options)

        if choice in extra_options:
            return choice

        if choice.endswith(self._CURRENT_DECK_SUFFIX):
            choice = choice[:-len(self._CURRENT_DECK_SUFFIX)]

        if choice not in names:
            self.frontend.error(f"No such deck: '{choice}'")
            return None

        return choice


    def _deck_interactive(self) -> str | None:
        exporter = self._storage_exporter()
        if not exporter:
            return None

        choice = self._pick_deck(exporter, "", [self._CREATE_NEW_DECK_OPTION])
        if choice is None:
            return None

        if choice == self._CREATE_NEW_DECK_OPTION:
            self.create()
            return None

        return choice


    def deck(self, name: str = None):
        if not name:
            name = self._deck_interactive()
            if not name:
                return

        self._load_state()
        self.state.current_deck = name
        self._save_state()


    def _storage_exporter(self) -> StorageExporter | None:
        exporter = self.exporters[self.config.app.deck_storage]
        if not isinstance(exporter, StorageExporter):
            self.frontend.error(f"Exporter '{self.config.app.deck_storage}' does not support managing decks.")
            return None
        return exporter


    def _prompt_side(self, prompt: str = "") -> str:
        options = ["Front side", "Back side", "Both sides"]
        choice = self.frontend.choice(prompt, options)
        return {"Front side": "front", "Back side": "back", "Both sides": "front,back"}[choice]


    def _prompt_grammar_rules(self, prompt: str = "") -> str:
        options = [r.value for r in GrammarRule]
        chosen = self.frontend.multi_choice(prompt, options)
        return ",".join(chosen)


    def _prompt_translate_direction(self, prompt: str = "") -> str | None:
        options = ["Front → Back", "Back → Front", "Auto (detect per note)"]
        choice = self.frontend.choice(prompt, options)
        return {"Front → Back": "front:back", "Back → Front": "back:front", "Auto (detect per note)": None}[choice]


    def _prompt_language(self, prompt: str) -> Language:
        languages = [l for l in Language if l != Language.NONE]
        options = [f"{l.value} ({l.short()})" for l in languages]
        while True:
            answer = self.frontend.choice(prompt, options)
            if answer in options:
                return languages[options.index(answer)]
            try:
                return Language.from_str(answer)
            except ValueError:
                self.frontend.error(f"Unknown language '{answer}'.")


    def _prompt_deck_metadata(self) -> dict:
        is_language_deck = self.frontend.input("Is it a deck for language learning? (y - yes, n - no)\n").lower() == "y"
        if is_language_deck:
            lang_front = self._prompt_language("Front side language:")
            lang_back = self._prompt_language("Back side language:")
        else:
            lang_front = lang_back = Language.NONE

        return {"lang_front": str(lang_front), "lang_back": str(lang_back)}


    def _create_interactive(self) -> tuple[str, dict] | None:
        name = self.frontend.input("Deck's name:\n").strip()
        metadata = self._prompt_deck_metadata()

        deck = Deck(name)
        deck.meta.update(metadata)
        self.frontend.show_deck_name(deck.name)
        self.frontend.show_deck_metadata(deck.meta)

        if self.frontend.input("Do you want to create this deck? (y - yes, n - no)\n").lower() != "y":
            return None

        return name, metadata


    def create(self, name: str = None, **metadata):
        if not name:
            result = self._create_interactive()
            if not result:
                return
            name, metadata = result

        if not name:
            self.frontend.error("Missing argument: name")
            return

        exporter = self._storage_exporter()
        if not exporter:
            return

        try:
            exporter.create_deck(name)
            if metadata:
                deck = Deck(name)
                deck.meta.update(metadata)
                exporter.export_deck(deck)
        except DeckOpError as e:
            self.frontend.error(str(e))
            return

        self.state.current_deck = name
        self._save_state()
        self.frontend.show_deck_name(self.state.current_deck)
        if metadata:
            self.frontend.show_deck_metadata(deck.meta)


    def delete(self, name: str = None):
        exporter = self._storage_exporter()
        if not exporter:
            return

        if not name:
            name = self._pick_deck(exporter, "")
            if not name:
                return

        if self.frontend.input(f"Delete deck '{name}' and all its notes? This can't be undone. (y - yes, n - no)\n").lower() != "y":
            return

        try:
            exporter.delete_deck(name)
        except DeckOpError as e:
            self.frontend.error(str(e))
            return

        if name == self.state.current_deck:
            self.state.current_deck = AppState().current_deck
            self._save_state()

        self.frontend.info(f"Deleted deck '{name}'")


    def _meta_interactive(self, deck: Deck) -> dict | None:
        metadata = self._prompt_deck_metadata()

        preview_meta = DeckMeta(deck.meta.to_dict())
        preview_meta.update(metadata)
        self.frontend.show_deck_name(deck.name)
        self.frontend.show_deck_metadata(preview_meta)

        if self.frontend.input("Do you want to save these changes? (y - yes, n - no)\n").lower() != "y":
            return None

        return metadata


    def meta(self, **kwargs):
        try:
            deck: Deck = self._load_deck()

            if not kwargs:
                kwargs = self._meta_interactive(deck)
                if kwargs is None:
                    return

            deck.meta.update(kwargs)

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
            if self.frontend.preview("Do you want to add this? (y - yes, n - no)\n", imported).lower() == "y":
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


    def _parse_apply_entry(self, entry: str) -> tuple[str, dict]:
        name, *args = entry.split()
        kwargs = dict(arg.split("=", 1) for arg in args if "=" in arg)
        return name, kwargs


    def _add_notes(self, entries: list[tuple[str, str, str, str]]):
        if not entries:
            return

        try:
            deck: Deck = self._load_deck()

            note_deck = Deck(deck.name)
            note_deck.meta = deck.meta

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

            if not note_deck.notes:
                return

            for entry in self.config.commands.add.apply:
                name, kwargs = self._parse_apply_entry(entry)
                if name not in self.transformers:
                    self.frontend.warning(f"Transformer '{name}' not found, skipping")
                    continue
                try:
                    self.transformers[name].transform_deck(note_deck, **kwargs)
                except DeckOpError as e:
                    self.frontend.warning(f"{e.operator.__class__.__name__}: {e}")

            if self.frontend.preview("Do you want to add this? (y - yes, n - no)\n", note_deck).lower() == "y":
                self._save_deck(deck + note_deck)

        except DeckOpError as e:
            self.frontend.error(str(e))
            return

        self._clear_temp_files()


    def add(self, front: str = None, back: str = None, model: str = None, tags: str = None):
        if front or back:
            self._add_notes([(front, back, model, tags)])
            return

        lines = self.frontend.input_multiline(
            "Enter notes as 'FRONT; BACK; MODEL; TAGS' (FRONT or BACK required). Press Enter on an empty line to finish."
        )
        entries = [self._parse_add_line(line) for line in lines]

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
            if self.frontend.preview("Do you want to save changes? (y - yes, n - no)\n", deck, result).lower() == "y":
                self._save_deck(deck)

        except DeckOpError as e:
            self.frontend.error(str(e))
            return


    def add_sound(self, side: str = None):
        self.transform("add-sound", side=side or self._prompt_side())


    def remove_sound(self, side: str = None):
        self.transform("remove-sound", side=side or self._prompt_side())

        self._clear_temp_files()


    def add_grammar(self, rule: str = None, side: str = None):
        self.transform(
            "add-grammar",
            rule=rule or self._prompt_grammar_rules("Grammar rule:"),
            side=side or self._prompt_side("Side:"),
        )


    def translate(self, side: str = None):
        if not side:
            side = self._prompt_translate_direction()
        self.transform("translate", side=side)


    def interactive(self):
        show_deck_option = "Show deck"
        actions = {
            show_deck_option: self.show,
            "Switch deck": self.deck,
            "Add cards": self.add,
            "Add sound to cards": self.add_sound,
            "Remove sound from cards": self.remove_sound,
            "Add grammar help to cards (articles, plulars etc.)": self.add_grammar,
            "Translate cards": self.translate,
            "Create new deck": self.create,
            "Delete deck": self.delete,
        }

        with self.frontend.fullscreen():
            while True:
                self.frontend.clear()
                self._load_state()

                try:
                    current_deck = self._load_deck()
                except DeckOpError as e:
                    self.frontend.error(str(e))
                    current_deck = Deck(self.state.current_deck)

                self.frontend.status_bar(self.version, current_deck)

                try:
                    choice = self.frontend.choice("", list(actions.keys()), transient=True, abortable=False)

                    actions[choice]()

                    if choice == show_deck_option:
                        self.frontend.hint("Enter back")
                        self.frontend.input("")
                except InteractiveAbort:
                    pass
