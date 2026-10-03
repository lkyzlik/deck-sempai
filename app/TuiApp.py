from typing import Callable

from app.App import App
from Deck import Deck
from DeckOperator import DeckOpError, DeckOpResult
from Enums import GrammarRule, Language
from exporters.StorageExporter import StorageExporter
from ui.frontend.Frontend import InteractiveAbort
from ui.frontend.TuiFrontend import TabSwitch, TuiFrontend


class TuiApp(App):
    """Adds the full-screen tabbed TUI on top of App's plain CLI commands."""

    # Lines taken up by status_bar() + tab_bar() + hint(), plus 1 of slack so a full-height tab
    # doesn't scroll the status bar off-screen.
    _CHROME_LINES = 7

    # Lines taken up by status_bar() + tab_bar() alone — for callees (preview()'s fullscreen
    # branch) that reserve their own trailing chrome instead of a single hint() line.
    _STATUS_TAB_LINES = 4

    def __init__(self):
        super().__init__()
        self._show_top_row = None
        # Mirrors what tui()'s loop last drew, so _preview_confirm_choice() can redraw the same
        # status bar/tab bar chrome before a preview takes over the rest of the screen.
        self._tab_names: list[str] = []
        self._current_tab = 0


    @staticmethod
    def _fit_top_row(total: int, height: int, pack: Callable[[int, int], object]) -> int:
        """Given `total` 1-indexed items packable a window at a time via `pack(top_row, height)`
        (returning an object with a `shown_notes` attribute counting how many items it actually fit,
        distinct from padding), returns the largest top_row — the smallest possible trailing window —
        whose packing still reaches `total`. Returns 1 if there's nothing to scroll (empty range)."""
        if total == 0:
            return 1

        top_row = total
        while top_row > 1:
            candidate = top_row - 1
            shown = pack(candidate, height).shown_notes
            if candidate + shown - 1 < total:
                break
            top_row = candidate
        return top_row


    def _load_deck_safe(self) -> Deck:
        try:
            return self._load_deck()
        except DeckOpError:
            return Deck(self.state.current_deck)


    def _refresh_integration_statuses(self) -> dict[str, str]:
        return {name: integration.status() for name, integration in self.integrations.items()}


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


    # In fullscreen, the deck preview wipes whatever the current tab has printed so far, redraws
    # the status bar/tab bar, and takes over the rest of the screen (scrollable, Enter accepts,
    # Backspace discards) instead of App's plain deck()+Yes/No choice().
    def _preview_confirm_choice(self, prompt: str, deck: Deck, result: DeckOpResult = None) -> bool:
        if not self.frontend.is_fullscreen:
            return super()._preview_confirm_choice(prompt, deck, result)
        self.frontend.clear()
        self.frontend.status_bar(self.version, self._load_deck_safe())
        self.frontend.tab_bar(self._tab_names, self._current_tab)
        height = max(1, self.frontend.terminal_height() - self._STATUS_TAB_LINES)
        return self.frontend.preview(prompt, deck, result, height=height)


    def _tab_show(self, tab_names: list[str], current_tab: int, current_deck: Deck) -> tuple[int, Deck]:
        total = len(current_deck.notes)
        height = max(1, self.frontend.terminal_height() - self._CHROME_LINES)

        def pack(top_row: int, h: int):
            return self.frontend.deck_notes(current_deck, top_row=top_row, height=h)

        max_top_row = self._fit_top_row(total, height, pack)
        if self._show_top_row is None:
            self._show_top_row = max_top_row
        else:
            # Clamp in case the deck shrank (or grew) since the remembered position was set.
            self._show_top_row = max(1, min(self._show_top_row, max_top_row))

        def remember(row: int):
            self._show_top_row = row

        self.frontend.deck(current_deck, include_header=False, top_row=self._show_top_row,
                           max_top_row=max_top_row, height=height, scrollable=True,
                           on_scroll=remember)
        return current_tab, self._load_deck_safe()


    def _tab_deck(self, tab_names: list[str], current_tab: int, current_deck: Deck) -> tuple[int, Deck]:
        exporter = self._storage_exporter()
        if not exporter:
            self.frontend.print("Deck management is not supported by the configured exporter.")
            self.frontend.hint("Tab next tab")
            self.frontend.choice("", [], transient=True, abortable=False)
            return current_tab, current_deck

        result = self._deck_options(exporter)
        if result is None:
            self.frontend.print("Could not load decks.")
            self.frontend.hint("Tab next tab")
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


    def _tab_integrations(self, tab_names: list[str], current_tab: int,
                           statuses: dict[str, str]) -> tuple[int, dict[str, str]]:
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
        return current_tab, statuses


    def tui(self):
        if not isinstance(self.frontend, TuiFrontend):
            self.frontend.error("The current frontend does not support the TUI.")
            return

        TAB_SHOW, TAB_DECK, TAB_ADD, TAB_TRANSFORM, TAB_INTEGRATIONS = range(5)
        tab_labels = ["Show", "Deck", "Add", "Transform", "Integrations"]

        current_tab = TAB_SHOW
        previous_tab = None
        current_deck = self._load_deck_safe()
        statuses = self._refresh_integration_statuses()

        with self.frontend.fullscreen():
            while True:
                self.frontend.clear()
                self._load_state()
                self.frontend.status_bar(self.version, current_deck)

                if current_tab == TAB_INTEGRATIONS and previous_tab != TAB_INTEGRATIONS:
                    statuses = self._refresh_integration_statuses()
                previous_tab = current_tab

                tab_names = list(tab_labels)
                if any(status == "disconnected" for status in statuses.values()):
                    tab_names[TAB_INTEGRATIONS] = "Integrations (!)"
                self.frontend.tab_bar(tab_names, current_tab)
                self._tab_names, self._current_tab = tab_names, current_tab

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
                        current_tab, statuses = self._tab_integrations(tab_names, current_tab, statuses)
                except InteractiveAbort:
                    pass
                except TabSwitch as e:
                    current_tab = (current_tab + (1 if e.key == "tab" else -1)) % len(tab_names)
