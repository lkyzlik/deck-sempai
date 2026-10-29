from deck_sempai.App import App
from deck_sempai.Deck import Deck
from deck_sempai.DeckOperator import DeckOpError, DeckOpResult
from deck_sempai.Enums import GrammarRule, Language
from deck_sempai.exporters.StorageExporter import StorageExporter
from deck_sempai.ui.Frontend import InteractiveAbort
from deck_sempai.ui.TuiFrontend import TabSwitch, TuiFrontend


class TuiApp(App):
    """Adds the full-screen tabbed TUI on top of App's plain CLI commands."""

    def __init__(self):
        super().__init__()
        self._show_top_row = None
        self._deck_load_failed = False


    def _load_deck_safe(self) -> Deck:
        try:
            deck = self._load_deck()
            self._deck_load_failed = False
            return deck
        except DeckOpError as e:
            self.frontend.print("Couldn't load deck. Repair in Integrations.")
            self.frontend.error(str(e))
            self._deck_load_failed = True
            return Deck(self.state.current_deck)


    def _refresh_integration_statuses(self) -> dict[str, str]:
        return {name: integration.status() for name, integration in self.integrations.items()}


    # Redraws the header with the given deck immediately, so a reload is reflected in the
    # "(N cards)" count right away instead of lagging a frame behind whatever's on screen.
    def _refresh_status_bar(self, current_deck: Deck):
        self.frontend.status_bar(self.version, current_deck, self._deck_load_failed)


    # Overrides of App's prompt helpers so backspace-abort also works when they're reused from
    # inside the tabbed UI (e.g. _tab_transform() -> add_sound() -> _prompt_side()). Plain CLI
    # calls still get abortable=False, since is_fullscreen is only true inside tui().
    def _pick_deck(self, exporter: StorageExporter, prompt: str, extra_options: list[str] = ()) -> str | None:
        result = self._deck_options(exporter)
        if result is None:
            return None
        names, suffixed = result

        options = suffixed + list(extra_options)

        choice = self.frontend.choice(prompt, options, abortable=self.frontend.is_fullscreen)

        if choice in extra_options:
            return choice

        if choice.endswith(self._CURRENT_DECK_SUFFIX):
            choice = choice[:-len(self._CURRENT_DECK_SUFFIX)]

        if choice not in names:
            self.frontend.error(f"No such deck: {choice!r}")
            return None

        return choice


    def _prompt_side(self, prompt: str = "") -> str:
        options = ["Front side", "Back side", "Both sides"]
        choice = self.frontend.choice(prompt, options, abortable=self.frontend.is_fullscreen)
        return {"Front side": "front", "Back side": "back", "Both sides": "front,back"}[choice]


    def _prompt_grammar_rules(self, prompt: str = "") -> str:
        options = [r.value for r in GrammarRule]
        chosen = self.frontend.choice_multi(prompt, options, abortable=self.frontend.is_fullscreen)
        return ",".join(chosen)


    def _prompt_translate_direction(self, prompt: str = "") -> str | None:
        options = ["Front → Back", "Back → Front", "Auto (detect per note)"]
        choice = self.frontend.choice(prompt, options, abortable=self.frontend.is_fullscreen)
        return {"Front → Back": "front:back", "Back → Front": "back:front", "Auto (detect per note)": None}[choice]


    def _prompt_language(self, prompt: str) -> Language:
        languages = [l for l in Language if l != Language.NONE]
        options = [f"{l.value} ({l.short()})" for l in languages]
        while True:
            answer = self.frontend.choice(prompt, options, abortable=self.frontend.is_fullscreen)
            if answer in options:
                return languages[options.index(answer)]
            try:
                return Language.from_str(answer)
            except ValueError:
                self.frontend.error(f"Unknown language {answer!r}.")


    # In fullscreen, the deck preview takes over the whole body (scrollable, Enter accepts,
    # Backspace discards) instead of App's plain deck()+Yes/No choice() — status bar/tab bar
    # stay put since preview() renders into the same persistent header/body/footer layout.
    def _preview_confirm_choice(self, prompt: str, deck: Deck, result: DeckOpResult = None) -> bool:
        if not self.frontend.is_fullscreen:
            return super()._preview_confirm_choice(prompt, deck, result)
        return self.frontend.preview(prompt, deck, result)


    # Reloads the deck for the Cards/Metadata tabs. On failure shows the error, waits for a key and
    # returns None.
    def _reload_tab_deck(self) -> Deck | None:
        try:
            current_deck = self._load_deck()
            self._deck_load_failed = False
        except DeckOpError as e:
            current_deck = Deck(self.state.current_deck)
            self._deck_load_failed = True
            self._refresh_status_bar(current_deck)
            self.frontend.print("Couldn't load deck. Repair in Integrations.")
            self.frontend.error(str(e))
            self.frontend.hint("Enter refresh · Tab next tab · Ctrl+C exit")
            self.frontend.choice("", [], transient=True, abortable=False)
            return None

        self._refresh_status_bar(current_deck)
        return current_deck


    def _tab_cards(self, tab_names: list[str], current_tab: int, current_deck: Deck) -> tuple[int, Deck]:
        def remember(row: int):
            self._show_top_row = row

        deck = self._reload_tab_deck()
        if deck is None:
            return current_tab, Deck(self.state.current_deck)

        self.frontend.deck(deck, include_header=False, top_row=self._show_top_row,
                           scrollable=True, on_scroll=remember)
        return current_tab, deck


    def _tab_meta(self, tab_names: list[str], current_tab: int, current_deck: Deck) -> tuple[int, Deck]:
        deck = self._reload_tab_deck()
        if deck is None:
            return current_tab, Deck(self.state.current_deck)

        self.frontend.deck_meta(deck.meta)
        self.frontend.hint("Enter edit · Tab next tab · Ctrl+C exit")
        self.frontend.choice("", [], transient=True, abortable=False)
        self.frontend.clear()
        self.meta()
        return current_tab, self._load_deck_safe()


    def _tab_decks(self, tab_names: list[str], current_tab: int, current_deck: Deck) -> tuple[int, Deck]:
        exporter = self._storage_exporter()
        if not exporter:
            self.frontend.print("Deck management is not supported by the configured exporter.")
            self.frontend.hint("Tab next tab · Ctrl+C exit")
            self.frontend.choice("", [], transient=True, abortable=False)
            return current_tab, current_deck

        result = self._deck_options(exporter)
        if result is None:
            self.frontend.print("Couldn't load decks. Repair in Integrations.")
            self.frontend.hint("Enter refresh · Tab next tab · Ctrl+C exit")
            self.frontend.choice("", [], transient=True, abortable=False)
            return current_tab, current_deck

        names, suffixed = result
        options = suffixed + [self._CREATE_NEW_DECK_OPTION, self._DELETE_DECK_OPTION]
        choice = self.frontend.choice("", options, transient=True, abortable=False)

        if choice == self._CREATE_NEW_DECK_OPTION:
            self.create()
        elif choice == self._DELETE_DECK_OPTION:
            self.delete()
        else:
            if choice.endswith(self._CURRENT_DECK_SUFFIX):
                choice = choice[:-len(self._CURRENT_DECK_SUFFIX)]
            self.deck(choice)

        return current_tab, self._load_deck_safe()


    def _tab_add(self, tab_names: list[str], current_tab: int, current_deck: Deck) -> tuple[int, Deck]:
        self.add()
        return current_tab, self._load_deck_safe()


    def _tab_transform(self, tab_names: list[str], current_tab: int, current_deck: Deck) -> tuple[int, Deck]:
        transform_actions = {
            "Add sound to cards": self.add_sound,
            "Remove sound from cards": self.remove_sound,
            "Add grammar help to cards (articles, plulars etc.)": self.add_grammar,
            "Translate cards": self.translate,
        }
        choice = self.frontend.choice("", list(transform_actions.keys()), transient=True, abortable=False)
        transform_actions[choice]()
        return current_tab, self._load_deck_safe()


    def _print_integrations(self, statuses: dict[str, str]):
        rows = [
            (i.name, statuses[i.name], i.user_help() if statuses[i.name] == "disconnected" else None)
            for i in self.integrations.values()
        ]
        self.frontend.integrations(rows)


    def status(self, integration: str = None):
        if not integration:
            self._print_integrations(self._refresh_integration_statuses())
            return
        target = self.integrations.get(integration.lower())
        if not target:
            self.frontend.error(f"Integration {integration!r} not found. Available integrations: {', '.join(self.integrations)}")
            return
        status = target.status()
        self.frontend.integrations([(target.name, status, target.user_help() if status == "disconnected" else None)])


    def _tab_integrations(self, tab_names: list[str], current_tab: int, current_deck: Deck,
                           statuses: dict[str, str]) -> tuple[int, Deck, dict[str, str]]:
        self._print_integrations(statuses)
        self.frontend.hint("Enter refresh · Tab next tab · Ctrl+C exit")
        choice = self.frontend.choice("", [], transient=True, abortable=False)
        if choice is None:
            statuses = self._refresh_integration_statuses()
            current_deck = self._load_deck_safe()
            self._refresh_status_bar(current_deck)
        return current_tab, current_deck, statuses


    def tui(self):
        if not isinstance(self.frontend, TuiFrontend):
            self.frontend.error("The current frontend does not support the TUI.")
            return

        TAB_CARDS, TAB_META, TAB_DECKS, TAB_ADD, TAB_TRANSFORM, TAB_INTEGRATIONS = range(6)
        tab_labels = ["Cards", "Metadata", "Decks", "Add", "Transform", "Integrations"]

        current_tab = TAB_CARDS
        previous_tab = None
        current_deck = self._load_deck_safe()
        statuses = self._refresh_integration_statuses()

        with self.frontend.fullscreen():
            while True:
                self.frontend.clear()
                self._load_state()
                self.frontend.status_bar(self.version, current_deck, self._deck_load_failed)

                if current_tab == TAB_INTEGRATIONS and previous_tab != TAB_INTEGRATIONS:
                    statuses = self._refresh_integration_statuses()
                previous_tab = current_tab

                tab_names = list(tab_labels)
                if any(status == "disconnected" for status in statuses.values()):
                    tab_names[TAB_INTEGRATIONS] = "Integrations (!)"
                self.frontend.tab_bar(tab_names, current_tab)

                try:
                    if current_tab == TAB_CARDS:
                        current_tab, current_deck = self._tab_cards(tab_names, current_tab, current_deck)
                    elif current_tab == TAB_META:
                        current_tab, current_deck = self._tab_meta(tab_names, current_tab, current_deck)
                    elif current_tab == TAB_DECKS:
                        current_tab, current_deck = self._tab_decks(tab_names, current_tab, current_deck)
                    elif current_tab == TAB_ADD:
                        current_tab, current_deck = self._tab_add(tab_names, current_tab, current_deck)
                    elif current_tab == TAB_TRANSFORM:
                        current_tab, current_deck = self._tab_transform(tab_names, current_tab, current_deck)
                    elif current_tab == TAB_INTEGRATIONS:
                        current_tab, current_deck, statuses = self._tab_integrations(
                            tab_names, current_tab, current_deck, statuses)
                except InteractiveAbort:
                    pass
                except TabSwitch as e:
                    current_tab = (current_tab + (1 if e.key in ("tab", "right") else -1)) % len(tab_names)
