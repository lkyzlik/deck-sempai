from typing import Protocol, runtime_checkable

from Enums import Language


class GrammarToolError(Exception):
    pass


class GrammarTool(Protocol):
    def __init__(self, lang: Language) -> None:
        self.lang = lang

    def extract_word(self, text: str) -> str:
        ...

    def pos(self, text: str) -> str:
        ...

    def noun_article(self, text: str) -> str:
        ...

    def noun_plural_suffix(self, text: str) -> str:
        ...

    def verb_tense(self, text: str, tense: str) -> str:
        ...
