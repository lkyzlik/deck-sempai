import re

from dataclasses import dataclass, field
from typing import Protocol, Self

from Enums import Side, Model, Language


class DeckMetaAttr(Protocol):
    def __str__(self) -> str:
        ...

    @classmethod
    def from_str(cls, value: str) -> Self:
        ...


class DeckMeta:
    def __init__(self, data: dict = {}):
        self.lang_front: Language = Language.NONE
        self.lang_back: Language = Language.NONE
        self.update(data)


    def update(self, data: dict):
        for key in data:
            if hasattr(self, key):
                value: DeckMetaAttr = getattr(self, key)
                new_value: DeckMetaAttr = type(value).from_str(data[key])
                setattr(self, key, new_value)


    def to_dict(self) -> dict:
        return {k: str(v) for k, v in vars(self).items()}


class Field:
    text: str
    sounds: list[str]

    FORMAT = "[TEXT]<br><br>[SOUNDS]"

    def __init__(self, label: str):
        # Store sound file names from [sound:...] tags
        self.sounds = re.findall(r'\[sound:([^\]]+)\]', label)
        # Remove [sound:...] tags
        self.text = re.sub(r'\[sound:[^\]]+\]', '', label)
        # Remove leading and trailing whitespace and <br> tags
        self.text = self._trim(self.text)

    @staticmethod
    def _trim(text: str) -> str:
        return re.sub(r'^(?:<br>\s*)+|(?:<br>\s*)+$', '', text).strip()

    def get_text_oneline(self) -> str:
        return self._trim(re.sub(r'\s+', ' ', self.text))

    def add_sound(self, sound_file: str) -> None:
        self.sounds.append(sound_file)

    def __str__(self) -> str:
        text = self.FORMAT.replace('[TEXT]', self.text)
        text = text.replace('[SOUNDS]', ''.join(f'[sound:{s}] ' for s in self.sounds).strip())
        return self._trim(text)


@dataclass
class Note:
    id: int | None
    front: Field
    back: Field
    model: Model = Model.BASIC_REVERSED
    tags: list[str] = field(default_factory=list)

    def get_field(self, side: Side) -> Field:
        return self.front if side == Side.FRONT else self.back

    # == operator to compare notes (ignoring model and tags)
    def __eq__(self, other):
        if not isinstance(other, Note):
            return NotImplemented
        return self.id == other.id if self.id and other.id else False


class Deck:
    def __init__(self, name: str = ""):
        self.name = name
        self.meta = DeckMeta()
        self.notes = []

    # + operator to combine decks
    def __add__(self, other):
        if not isinstance(other, Deck):
            return NotImplemented
        for note in other.notes:
            if note not in self.notes:
                self.notes.append(note)
        return self