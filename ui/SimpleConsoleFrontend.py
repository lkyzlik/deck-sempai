from Deck import Deck, DeckMeta, Field
from DeckOperator import DeckOpResult

from ui.Logger import LoggerProgress


class SimpleProgress:
    def __init__(self):
        self._totals: dict[int, int] = {}
        self._completed: dict[int, int] = {}
        self._descriptions: dict[int, str] = {}
        self._next_id = 0
        self._active = False


    def __enter__(self) -> "SimpleProgress":
        return self


    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._active:
            print()
        return False


    def add_task(self, description: str, total: int) -> int:
        task_id = self._next_id
        self._next_id += 1
        self._totals[task_id] = total
        self._completed[task_id] = 0
        self._descriptions[task_id] = description
        self._render(task_id)
        return task_id


    def update(self, task_id: int, advance: int = 0, description: str = None):
        if description is not None:
            self._descriptions[task_id] = description
        self._completed[task_id] += advance
        self._render(task_id)


    def _render(self, task_id: int):
        self._active = True
        print(f"\r{self._descriptions[task_id]} ({self._completed[task_id]}/{self._totals[task_id]})", end="", flush=True)


class SimpleConsoleFrontend:
    """
    Plain-text frontend: ASCII console output only, no colors or unicode.
    """

    def _field_to_str(self, field: Field) -> str:
        return field.get_text_oneline() + " [snd]" * len(field.sounds)


    def print(self, message: str):
        print(message)


    def info(self, message: str):
        print(f"Info: {message}")


    def warning(self, message: str):
        print(f"Warning: {message}")


    def error(self, message: str):
        print(f"Error: {message}")


    def progress(self) -> LoggerProgress:
        return SimpleProgress()


    def show_deck(self, deck: Deck, result: DeckOpResult = None,
                  include_metadata: bool = True, max_rows: int = None):

        # Validate max_rows
        if max_rows and (max_rows > len(deck.notes) or max_rows < 0):
            self.warning(f"Can't show {max_rows} rows. Showing all notes instead.")
            max_rows = None

        if include_metadata:
            self.show_deck_name(deck.name)
            self.show_deck_metadata(deck.meta)

        notes = deck.notes[:max_rows] if max_rows else deck.notes
        show_index = len(notes) > 1

        headers = ["#", "Front", "Back"] if show_index else ["Front", "Back"]
        if result:
            headers.append(result.op_title)

        rows = []
        for i, note in enumerate(notes):
            row = [str(i + 1)] if show_index else []
            row += [self._field_to_str(note.front), self._field_to_str(note.back)]
            if result:
                note_result = result.note_results[i]
                row.append("OK" if note_result.success else "FAIL")
            rows.append(row)

        self._print_table(headers, rows)


    def _print_table(self, headers: list[str], rows: list[list[str]]):
        widths = [len(header) for header in headers]
        for row in rows:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], len(cell))

        def format_row(cells: list[str]) -> str:
            return "| " + " | ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells)) + " |"

        separator = "+-" + "-+-".join("-" * width for width in widths) + "-+"

        print(separator)
        print(format_row(headers))
        print(separator)
        for row in rows:
            print(format_row(row))
        print(separator)


    def preview(self, prompt: str, deck: Deck, result: DeckOpResult = None) -> str:
        self.show_deck(deck, result, include_metadata=False)
        return self.input(prompt)


    def input(self, prompt: str) -> str:
        return input(prompt)


    def input_multiline(self, prompt: str) -> list[str]:
        self.print(prompt)
        lines = []
        while True:
            line = self.input("> ").strip()
            if not line:
                break
            lines.append(line)
        return lines


    def choice(self, prompt: str, options: list[str]) -> str:
        if prompt:
            self.print(prompt)
        for i, option in enumerate(options, 1):
            print(f"{i}. {option}")

        answer = self.input("> ").strip()
        if answer.isdigit() and 1 <= int(answer) <= len(options):
            return options[int(answer) - 1]
        return answer


    def show_deck_metadata(self, meta: DeckMeta):
        for key, value in meta.to_dict().items():
            print(f"{key}: {value}")


    def show_deck_name(self, name: str):
        print(f"Deck: {name}")
