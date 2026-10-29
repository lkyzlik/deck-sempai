from dataclasses import dataclass
from typing import Literal

from deck_sempai.ui.Logger import Logger


NoteOpStatus = Literal["ok", "failed", "skipped"]

# Precedence used when combining mutiple results for the same note
_STATUS_PRECEDENCE: tuple[NoteOpStatus, ...] = ("failed", "ok", "skipped")


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
    status: NoteOpStatus

    def __add__(self, other: 'NoteOpResult') -> 'NoteOpResult':
        for status in _STATUS_PRECEDENCE:
            if self.status == status or other.status == status:
                return NoteOpResult(status)
        return NoteOpResult("ok")


@dataclass
class DeckOpResult:
    """Result of an operation (op) performed on a deck"""
    note_results: list[NoteOpResult]
    op_title: str = "Results"

    @staticmethod
    def all_with_status(n_notes: int, status: NoteOpStatus, op_title: str = "Results") -> 'DeckOpResult':
        return DeckOpResult([NoteOpResult(status) for _ in range(n_notes)], op_title=op_title)
