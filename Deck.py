import re

from dataclasses import dataclass, field
from enum import StrEnum

# String enum for model
class Model(StrEnum):
    BASIC = "Basic"
    BASIC_REVERSED = "Basic (and reversed card)"
    BASIC_OPT_REVERSED = "Basic (optional reversed card)"
    BASIC_TYPE = "Basic (type in the answer)"
    CLOZE = "Cloze"
    IMAGE = "Image Occlusion Enhanced"


class Field:
    text: str
    sounds: list[str]

    FORMAT = "[TEXT]<br><br>[SOUNDS]"

    def __init__(self, text: str):
        # Store sound file names from [sound:...] tags
        self.sounds = re.findall(r'\[sound:([^\]]+)\]', text)
        # Remove [sound:...] tags
        self.text = re.sub(r'\[sound:[^\]]+\]', '', text)
        # Remove trailing newlines
        self.text = re.sub(r'(?:<br>\s*)+$', '', self.text)
        # Remove whitespace around
        self.text = self.text.strip()

    def get_text_oneline(self) -> str:
        return re.sub(r'\s+', ' ', self.text).strip()

    def add_sound(self, sound_file: str) -> None:
        self.sounds.append(sound_file)

    def __str__(self) -> str:
        sounds_str = ''.join(f'[sound:{s}] ' for s in self.sounds).strip()
        return self.FORMAT.replace('[TEXT]', self.text).replace('[SOUNDS]', sounds_str)


@dataclass
class Note:
    id: int | None
    front: Field
    back: Field
    model: Model = Model.BASIC_REVERSED
    tags: list[str] = field(default_factory=list)

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