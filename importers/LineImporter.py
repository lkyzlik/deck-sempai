from Deck import Card, Deck, Model, Note
from importers.Importer import Importer, ImporterError

class LineImporter(Importer):
    def __init__(self):
        self.name = "line"


    # import line FRONT [BACK] [MODEL] [TAG1,TAG2,...]
    def import_deck(self, *args) -> Deck:
        front = args[0] if 0 < len(args) else None
        back = args[1] if 1 < len(args) else ""
        model = args[2] if 2 < len(args) else Model.BASIC_REVERSED
        tags = args[3].split(",") if 3 < len(args) else []

        if not front:
            raise ImporterError(self, "Missing argument 1: front text")
        
        deck = Deck()
        deck.notes.append(Note(None, Card(front), Card(back), model, tags))

        return deck