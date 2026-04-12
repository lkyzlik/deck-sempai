from enum import StrEnum


class AliasedStrEnum(StrEnum):
    def __new__(cls, value: str, short: str, *other: str):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj._short = short
        obj._aliases = set(other + (value, short))
        return obj

    @classmethod
    def _missing_(cls, value: object) -> "AliasedStrEnum | None":
        if not isinstance(value, str):
            return None
        for member in cls:
            if value.lower() in (a.lower() for a in member._aliases):
                return member
        return None
    
    def short(self) -> str:
        return self._short
    

class Language(AliasedStrEnum):
    ENGLISH = "English", "en"
    DANISH = "Danish", "da", "dansk"