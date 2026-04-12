from Deck import Deck, Field, Model, Note
from importers.Importer import Importer, ImporterError

class LineImporter(Importer):
    def __init__(self):
        self.name = "line"


    def import_deck(self, front: str = None, back: str = "",
                    model: str = Model.BASIC_REVERSED,
                    tags: list[str] = []) -> Deck:
        if not front:
            raise ImporterError(self, "Missing keyword argument: front")
        
        deck = Deck()
        deck.notes.append(Note(None, Field(front), Field(back), model, tags))

        return deck
