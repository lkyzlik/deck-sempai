from dataclasses import dataclass

from interfaces.Logger import Logger


class DeckOperator:
    """Base class for anything that operates on a deck"""
    def __init__(self, logger: Logger):
        self.logger = logger

    def _info(self, message: str):
        self.logger.info(f"{self.__class__.__name__}: {message}")

    def _warning(self, message: str):
        self.logger.warning(f"{self.__class__.__name__}: {message}")


class DeckOpError(Exception):
    def __init__(self, operator: DeckOperator, message: str):
        super().__init__(message)
        self.operator = operator


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