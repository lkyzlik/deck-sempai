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


@dataclass
class Card:
    text: str
    sound: str = ""
        

@dataclass
class Note:
    id: int | None
    front: Card
    back: Card
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