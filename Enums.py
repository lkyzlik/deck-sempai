from typing import Self
from enum import StrEnum


class AliasedStrEnum(StrEnum):
    def __new__(cls, value: str, short: str, *other: str):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj._short = short
        obj._aliases = set(other + (value, short))
        return obj

    @classmethod
    def _missing_(cls, value: object) -> Self | None:
        if not isinstance(value, str):
            return None
        for member in cls:
            if value.lower() in (a.lower() for a in member._aliases):
                return member
        return None
    
    def short(self) -> str:
        return self._short
    
    def __str__(self) -> str:
        return self.value

    @classmethod
    def from_str(cls, value: str) -> Self:
        return cls(value)


class Language(AliasedStrEnum):
    NONE = "none", "x"
    DANISH = "Danish", "da-DK", "da"
    ENGLISH_GB = "English - British", "en-GB", "English", "en"
    ENGLISH_US = "English - American", "en-US"
    GERMAN_DE = "German - Germany", "de-DE", "German", "de"
    SPANISH_ES = "Spanish - Spain", "es-ES", "Spanish", "es"


class Side(AliasedStrEnum):
    FRONT = "front", "f"
    BACK = "back", "b"


class Model(AliasedStrEnum):
    BASIC = "Basic", "b"
    BASIC_REVERSED = "Basic (and reversed card)", "br"
    BASIC_OPT_REVERSED = "Basic (optional reversed card)", "bor"
    BASIC_TYPE = "Basic (type in the answer)", "ba"
    CLOZE = "Cloze", "c"
    IMAGE = "Image Occlusion", "img"


class GrammarRule(AliasedStrEnum):
    NOUN_ARTICLE = "noun_article", "na"
    NOUN_PLURAL = "noun_plural", "np"
    VERB_TENSES = "verb_tenses", "vt"
    VERB_INFINITIVE = "verb_infinitive", "vi"
