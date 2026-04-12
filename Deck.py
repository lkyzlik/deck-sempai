import re

from dataclasses import dataclass, field
from enum import StrEnum

from Enums import Side, Model


class Field:
    text: str
    sounds: list[str]

    FORMAT = "[TEXT]<br><br>[SOUNDS]"

    def __init__(self, text: str):
        # Store sound file names from [sound:...] tags
        self.sounds = re.findall(r'\[sound:([^\]]+)\]', text)
        # Remove [sound:...] tags
        self.text = re.sub(r'\[sound:[^\]]+\]', '', text)
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
    

@dataclass
class Deck:
    name: str = ""
    notes: list[Note] = field(default_factory=list)

    # + operator to combine decks
    def __add__(self, other):
        if not isinstance(other, Deck):
            return NotImplemented
        for note in other.notes:
            if note not in self.notes:
                self.notes.append(note)
        return self