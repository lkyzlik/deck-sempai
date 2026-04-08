from dataclasses import dataclass


@dataclass
class NoteOpResult:
    """Result of an operation (op) performed on a note"""
    success: bool


@dataclass
class DeckOpResult:
    """Result of an operation (op) performed on a deck"""
    note_results: list[NoteOpResult]
    op_title: str = "Results"

    @staticmethod
    def all_ok(n_notes: int, op_title: str = "Results") -> 'DeckOpResult':
        return DeckOpResult([NoteOpResult(True) for _ in range(n_notes)], op_title=op_title)