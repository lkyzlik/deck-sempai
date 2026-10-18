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
from ui.Frontend import Frontend
from ui.RichTuiFrontend import RichTuiFrontend

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
    _DELETE_DECK_OPTION = "Delete deck"
    _CURRENT_DECK_SUFFIX = " (current)"

    def __init__(self):
        self.config = Config.load()
        self.state = AppState()

        with open(Path(__file__).parent.parent / "pyproject.toml", "rb") as f:
            self.version = tomllib.load(f)["project"]["version"]

        data_dir = Path(user_data_dir("deck-sempai"))
        self.state_file = data_dir / "state.json"
        self.media_dir = data_dir / "media"

        self.frontends: dict[str, Frontend] = {
            "rich": RichTuiFrontend(log_level=self.config.app.log_level),
        }
        self.frontend: Frontend = self.frontends[self.config.app.frontend]

        # Integrations
        self.integrations : dict[str, Integration] = {}
        for integration_cls in (AnkiIntegration, OllamaIntegration, OrdnetIntegration):
            integration = integration_cls()
            integration_config = self.config.integrations.get(integration.name, {})
            integration.configure(integration_config)
            integration.enable(integration_config.get("enable", True))
            self.integrations[integration.name] = integration

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


    def _deck_options(self, exporter: StorageExporter) -> tuple[list[str], list[str]] | None:
        try:
            names = sorted(exporter.get_decks())
        except DeckOpError as e:
            self.frontend.error(str(e))
            return None

        suffixed = [n + (self._CURRENT_DECK_SUFFIX if n == self.state.current_deck else "") for n in names]
        return names, suffixed


    def _pick_deck(self, exporter: StorageExporter, prompt: str, extra_options: list[str] = ()) -> str | None:
        result = self._deck_options(exporter)
        if result is None:
            return None
        names, suffixed = result

        options = suffixed + list(extra_options)

        choice = self.frontend.choice(prompt, options, abortable=False)

        if choice in extra_options:
            return choice

        if choice.endswith(self._CURRENT_DECK_SUFFIX):
            choice = choice[:-len(self._CURRENT_DECK_SUFFIX)]

        if choice not in names:
            self.frontend.error(f"No such deck: {choice!r}")
            return None

        return choice


    def _deck_interactive(self) -> str | None:
        exporter = self._storage_exporter()
        if not exporter:
            return None

        choice = self._pick_deck(exporter, "", [self._CREATE_NEW_DECK_OPTION, self._DELETE_DECK_OPTION])
        if choice is None:
            return None

        if choice == self._CREATE_NEW_DECK_OPTION:
            self.create()
            return None

        if choice == self._DELETE_DECK_OPTION:
            self.delete()
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
            self.frontend.error(f"Exporter {self.config.app.deck_storage!r} does not support managing decks.")
            return None
        return exporter


    def _prompt_side(self, prompt: str = "") -> str:
        options = ["Front side", "Back side", "Both sides"]
        choice = self.frontend.choice(prompt, options, abortable=False)
        return {"Front side": "front", "Back side": "back", "Both sides": "front,back"}[choice]


    def _prompt_grammar_rules(self, prompt: str = "") -> str:
        options = [r.value for r in GrammarRule]
        chosen = self.frontend.choice_multi(prompt, options, abortable=False)
        return ",".join(chosen)


    def _prompt_translate_direction(self, prompt: str = "") -> str | None:
        options = ["Front → Back", "Back → Front", "Auto (detect per note)"]
        choice = self.frontend.choice(prompt, options, abortable=False)
        return {"Front → Back": "front:back", "Back → Front": "back:front", "Auto (detect per note)": None}[choice]


    def _prompt_language(self, prompt: str) -> Language:
        languages = [l for l in Language if l != Language.NONE]
        options = [f"{l.value} ({l.short()})" for l in languages]
        while True:
            answer = self.frontend.choice(prompt, options, abortable=False)
            if answer in options:
                return languages[options.index(answer)]
            try:
                return Language.from_str(answer)
            except ValueError:
                self.frontend.error(f"Unknown language {answer!r}.")


    def _confirm(self, prompt: str) -> bool:
        return self.frontend.choice(prompt, ["Yes", "No"], abortable=False) == "Yes"


    # Plain y/n confirmation for a command run non-interactively (its own argument was given
    # directly) — unlike _confirm() above, this keeps the plain input() prompt, matching whatever
    # argument-less interactive fallback would otherwise have used choice() for. Callers compute
    # whether they're in the interactive case themselves and pick between this and _confirm().
    def _confirm_plain(self, prompt: str) -> bool:
        return self.frontend.input(f"{prompt} (y - yes, n - no)\n").lower() == "y"


    def _preview_confirm(self, prompt: str, deck: Deck, result: DeckOpResult = None) -> bool:
        return self.frontend.preview(prompt, deck, result)


    def _preview_confirm_choice(self, prompt: str, deck: Deck, result: DeckOpResult = None) -> bool:
        self.frontend.deck(deck, result, include_header=False)
        return self.frontend.choice(prompt, ["Yes", "No"], abortable=False) == "Yes"


    def _prompt_deck_metadata(self) -> dict:
        is_language_deck = self._confirm("Is it a deck for language learning?")
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
        self.frontend.deck_name(deck.name)
        self.frontend.deck_meta(deck.meta)

        if not self._confirm("Do you want to create this deck?"):
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
        self.frontend.deck_name(self.state.current_deck)
        if metadata:
            self.frontend.deck_meta(deck.meta)


    def delete(self, name: str = None):
        exporter = self._storage_exporter()
        if not exporter:
            return

        interactive = not name
        if not name:
            name = self._pick_deck(exporter, "")
            if not name:
                return

        confirm = self._confirm if interactive else self._confirm_plain
        if not confirm(f"Delete deck {name!r} and all its notes? This can't be undone."):
            return

        try:
            exporter.delete_deck(name)
        except DeckOpError as e:
            self.frontend.error(str(e))
            return

        if name == self.state.current_deck:
            self.state.current_deck = AppState().current_deck
            self._save_state()


    def _meta_interactive(self, deck: Deck) -> dict | None:
        metadata = self._prompt_deck_metadata()

        preview_meta = DeckMeta(deck.meta.to_dict())
        preview_meta.update(metadata)
        self.frontend.deck_name(deck.name)
        self.frontend.deck_meta(preview_meta)

        if not self._confirm("Do you want to save these changes?"):
            return None

        return metadata


    def meta(self, **kwargs):
        try:
            deck: Deck = self._load_deck()

            if not kwargs:
                kwargs = self._meta_interactive(deck)
                if kwargs is None:
                    return

            unknown = [key for key in kwargs if key not in DeckMeta.DEFAULTS]
            if unknown:
                self.frontend.error(f"Unknown metadata key(s): {', '.join(unknown)}. "
                                    f"Valid keys: {', '.join(DeckMeta.DEFAULTS)}")
                return

            deck.meta.update(kwargs, self.frontend)

            self.frontend.deck_meta(deck.meta)

            self._save_deck(deck)
        except DeckOpError as e:
            self.frontend.error(str(e))
            return


    def export(self, exporter: str, **kwargs):
        if exporter not in self.exporters:
            self.frontend.error(f"Exporter {exporter!r} not found. Available exporters: {', '.join(self.exporters.keys())}")
            return

        try:
            deck: Deck = self._load_deck()
            result: DeckOpResult = self.exporters[exporter].export_deck(deck, **kwargs)
            self.frontend.deck(deck, result)
        except DeckOpError as e:
            self.frontend.error(str(e))
            return


    def import_(self, importer: str, **kwargs):
        if importer not in self.importers:
            self.frontend.error(f"Importer {importer!r} not found. Available importers: {', '.join(self.importers.keys())}")
            return

        try:
            imported: Deck = self.importers[importer].import_deck(**kwargs)
            if self._preview_confirm("Do you want to add this?", imported):
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


    def _add_notes(self, entries: list[tuple[str, str, str, str]], interactive: bool):
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
                    self.frontend.warning(f"Transformer {name!r} not found")
                    continue
                try:
                    self.transformers[name].transform_deck(note_deck, **kwargs)
                except DeckOpError as e:
                    self.frontend.warning(f"{e.operator.__class__.__name__}: {e}")

            confirm_preview = self._preview_confirm_choice if interactive else self._preview_confirm
            if confirm_preview("Do you want to add this?", note_deck):
                self._save_deck(deck + note_deck)

        except DeckOpError as e:
            self.frontend.error(str(e))
            return

        self._clear_temp_files()


    def add(self, front: str = None, back: str = None, model: str = None, tags: str = None):
        if front or back:
            self._add_notes([(front, back, model, tags)], interactive=False)
            return

        lines = self.frontend.input_multi(
                "Input one card per line:", newline_hint="front text ; back text"
        )
        entries = [self._parse_add_line(line) for line in lines]

        self._add_notes(entries, interactive=True)


    def show(self, only_meta: bool = False):
        try:
            deck: Deck = self._load_deck()
            if only_meta:
                self.frontend.deck_name(deck.name)
                self.frontend.deck_meta(deck.meta)
            else:
                self.frontend.deck(deck)

        except DeckOpError as e:
            self.frontend.error(str(e))
            return


    def transform(self, transformer: str, interactive: bool = False, **kwargs):
        if transformer not in self.transformers:
            self.frontend.error(f"Transformer {transformer!r} not found. Available transformers: {', '.join(self.transformers.keys())}")
            return

        try:
            deck: Deck = self._load_deck()
            result: DeckOpResult = self.transformers[transformer].transform_deck(deck, **kwargs)
            confirm_preview = self._preview_confirm_choice if interactive else self._preview_confirm
            if confirm_preview("Do you want to save changes?", deck, result):
                self._save_deck(deck)

        except DeckOpError as e:
            self.frontend.error(str(e))
            return


    def add_sound(self, side: str = None):
        interactive = not side
        self.transform("add-sound", side=side or self._prompt_side(), interactive=interactive)


    def remove_sound(self, side: str = None):
        interactive = not side
        self.transform("remove-sound", side=side or self._prompt_side(), interactive=interactive)

        self._clear_temp_files()


    def add_grammar(self, rule: str = None, side: str = None):
        interactive = not rule or not side
        self.transform(
            "add-grammar",
            rule=rule or self._prompt_grammar_rules("Grammar rule:"),
            side=side or self._prompt_side("Side:"),
            interactive=interactive,
        )


    def translate(self, side: str = None):
        interactive = not side
        if not side:
            side = self._prompt_translate_direction()
        self.transform("translate", side=side, interactive=interactive)
