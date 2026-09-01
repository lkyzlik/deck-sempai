import re

from typing import Protocol, runtime_checkable

from Enums import Language


class GrammarToolError(Exception):
    pass


class GrammarTool(Protocol):
    def __init__(self, lang: Language) -> None:
        self.lang = lang

    def extract_word(self, text: str) -> str:
        # Remove any text in braces (), [], <>, {}
        text = re.sub(r'[\(\[\{<][^)\]\}>]*[\)\]\}>]', '', text)
        # Remove Danish articles and infinitive markers
        text = re.sub(r'^(en|et|den|det|at)\s+', '', text, flags=re.IGNORECASE)
        # Remove numbers
        text = re.sub(r'\d+', '', text)
        # Remove punctuation
        text = re.sub(r'[^\w\s]', '', text)
        # Remove whitespace around
        text = text.strip()
        # We should be left with a single word
        words = text.split()
        if len(words) != 1:
            raise GrammarToolError(f"Can't extract a single word from {text!r}")
        return words[0]

    def pos(self, text: str) -> str:
        ...

    def noun_article(self, text: str) -> str:
        ...

    def noun_plural_suffix(self, text: str, definite: bool = False) -> str:
        ...

    def verb_tense(self, text: str, tense: str) -> str:
        ...
