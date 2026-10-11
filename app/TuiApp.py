from app.App import App
from Deck import Deck
from DeckOperator import DeckOpError, DeckOpResult
from Enums import GrammarRule, Language
from exporters.StorageExporter import StorageExporter
from ui.frontend.Frontend import InteractiveAbort
from ui.frontend.TuiFrontend import TabSwitch, TuiFrontend


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
            self.frontend.error(f"No such deck: '{choice}'")
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
                self.frontend.error(f"Unknown language '{answer}'.")


    # In fullscreen, the deck preview takes over the whole body (scrollable, Enter accepts,
    # Backspace discards) instead of App's plain deck()+Yes/No choice() — status bar/tab bar
    # stay put since preview() renders into the same persistent header/body/footer layout.
    def _preview_confirm_choice(self, prompt: str, deck: Deck, result: DeckOpResult = None) -> bool:
        if not self.frontend.is_fullscreen:
            return super()._preview_confirm_choice(prompt, deck, result)
        return self.frontend.preview(prompt, deck, result)


    def _tab_show(self, tab_names: list[str], current_tab: int, current_deck: Deck) -> tuple[int, Deck]:
        def remember(row: int):
            self._show_top_row = row

        try:
            current_deck = self._load_deck()
            self._deck_load_failed = False
        except DeckOpError as e:
            current_deck = Deck(self.state.current_deck)
            self._deck_load_failed = True
            self._refresh_status_bar(current_deck)
            self.frontend.print("Couldn't load deck. Repair in Integrations.")
            self.frontend.error(str(e))
            self.frontend.hint("Enter refresh · Tab next tab")
            self.frontend.choice("", [], transient=True, abortable=False)
            return current_tab, current_deck

        self._refresh_status_bar(current_deck)
        self.frontend.deck(current_deck, include_header=False, top_row=self._show_top_row,
                           scrollable=True, on_scroll=remember)
        return current_tab, current_deck


    def _tab_deck(self, tab_names: list[str], current_tab: int, current_deck: Deck) -> tuple[int, Deck]:
        exporter = self._storage_exporter()
        if not exporter:
            self.frontend.print("Deck management is not supported by the configured exporter.")
            self.frontend.hint("Tab next tab")
            self.frontend.choice("", [], transient=True, abortable=False)
            return current_tab, current_deck

        result = self._deck_options(exporter)
        if result is None:
            self.frontend.print("Couldn't load decks. Repair in Integrations.")
            self.frontend.hint("Enter refresh · Tab next tab")
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


    def _tab_integrations(self, tab_names: list[str], current_tab: int, current_deck: Deck,
                           statuses: dict[str, str]) -> tuple[int, Deck, dict[str, str]]:
        visible = [i for i in self.integrations.values() if statuses.get(i.name) != "disabled"]
        if not visible:
            self.frontend.print("No integrations require attention.")
        else:
            rows = [
                (i.name, statuses[i.name], i.user_help() if statuses[i.name] == "disconnected" else None)
                for i in visible
            ]
            self.frontend.integrations(rows)

        self.frontend.hint("Enter refresh · Tab next tab")
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

        TAB_SHOW, TAB_DECK, TAB_ADD, TAB_TRANSFORM, TAB_INTEGRATIONS = range(5)
        tab_labels = ["Cards", "Deck", "Add", "Transform", "Integrations"]

        current_tab = TAB_SHOW
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
                    if current_tab == TAB_SHOW:
                        current_tab, current_deck = self._tab_show(tab_names, current_tab, current_deck)
                    elif current_tab == TAB_DECK:
                        current_tab, current_deck = self._tab_deck(tab_names, current_tab, current_deck)
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
