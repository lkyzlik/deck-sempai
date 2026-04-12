from Deck import Deck, Field, Model, Note
from importers.Importer import Importer, ImporterError

class LineImporter(Importer):
    def __init__(self):
        self.name = "line"


    def _import_deck(self, front: str, back: str, model: Model, tags: list[str]) -> Deck:
        deck = Deck()
        deck.notes.append(Note(None, Field(front), Field(back), model, tags))
        return deck


    def import_deck(self, front: str = None, back: str = "",
                    model: str = Model.BASIC_REVERSED,
                    tags: str = None) -> Deck:
        if not front:
            raise ImporterError(self, "Missing argument: front")

        try:
            model = Model(model)
        except ValueError:
            raise ImporterError(self, f"Invalid argument: model={model!r}, supported: {', '.join([m.value for m in Model])}")

        tags = [t.strip() for t in tags.split(',')] if tags else []

        return self._import_deck(front, back, model, tags)
