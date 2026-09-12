import typer
from typing import Optional

from App import App
from Deck import Side
from Enums import GrammarRule, Model

CTX_SETTINGS = {"allow_extra_args": True, "ignore_unknown_options": True}


app = App()
cli = typer.Typer()


def get_kwargs(ctx: typer.Context) -> dict:
    parsed = {}
    for arg in ctx.args:
        if "=" in arg:
            key, value = arg.split("=", 1)
            parsed[key] = value
    return parsed


@cli.command(context_settings=CTX_SETTINGS)
def meta(ctx: typer.Context):
    """
    Update the current deck's metadata with the provided keyword arguments.
    If no keyword arguments are provided, show the current metadata.
    """
    app.meta(**get_kwargs(ctx))


@cli.command()
def deck(name: Optional[str] = typer.Argument(None, help="Name of the deck to switch to. If omitted, shows the current deck.")):
    """
    Set the current deck to work with. If no NAME is provided, shows the current deck.
    """
    app.deck(name)


@cli.command(context_settings=CTX_SETTINGS)
def export(ctx: typer.Context, exporter: str = typer.Argument(help="Name of the exporter to use.")):
    """
    Export the current deck using the specified EXPORTER.
    Additional keyword arguments can be passed to the exporter.
    """
    app.export(exporter, **get_kwargs(ctx))


# 'import' is a reserved keyword in Python, so we use 'import_' instead
@cli.command("import", context_settings=CTX_SETTINGS)
def import_(ctx: typer.Context, importer: str = typer.Argument(help="Name of the importer to use.")):
    """
    Import a deck using the specified IMPORTER.
    Additional keyword arguments can be passed to the importer.
    """
    app.import_(importer, **get_kwargs(ctx))


@cli.command()
def add(front: Optional[str] = typer.Argument(None, help="Front text of the new note. Filled in via translation if omitted (requires --back)."),
        back: Optional[str] = typer.Option(None, "--back", "-b", help="Back text of the new note. Filled in via translation if omitted (requires FRONT)."),
        model: Optional[str] = typer.Option(None, "--model", "-m", help=f"Note model: {', '.join([m.value for m in Model])}"),
        tags: Optional[str] = typer.Option(None, "--tags", "-t", help="Comma-separated tags to add to the note.")):
    """
    Add a new note with the given FRONT and/or BACK text. Whichever side is omitted is
    filled in via translation from the other; at least one must be given. Pronunciation
    sound and grammar help are then added to both sides (skipped on a side whose language
    doesn't support them).

    If called with neither FRONT nor --back, enters an interactive mode where notes can
    be entered one per line as 'FRONT; BACK; MODEL; TAGS' (FRONT or BACK required),
    until 'q' is entered.
    """
    app.add(front, back, model, tags)


@cli.command()
def show():
    """
    Show the current deck.
    """
    app.show()


@cli.command()
def sound(side: str = typer.Argument(help=f"Side of the card: {', '.join([s.value for s in Side])}"),
          delete: bool = typer.Option(False, "--delete", "-d", help="Remove sound instead of adding it.")):
    """
    Add sound to the specified SIDE of the current deck.
    Use --delete/-d to remove sounds instead.
    """
    if delete:
        app.transform("remove-sound", side=side)
    else:
        app.transform("add-sound", side=side)


@cli.command()
def grammar(grammar_rule: str = typer.Argument(help=f"Comma-separated grammar help rules: {', '.join([g.value for g in GrammarRule])}"),
            side: str = typer.Argument(help=f"Side of the card: {', '.join([s.value for s in Side])}")):
    """
    Add grammar help of the specified GRAMMAR_RULE(s) to the specified SIDE of the current deck.
    Multiple rules can be combined as a comma-separated list, e.g. 'noun_article,noun_plural'.
    """
    app.transform("add-grammar", grammar_rule=grammar_rule, side=side)


@cli.command()
def translate(side: Optional[str] = typer.Argument(None, help=f"Direction to translate: FROM-TO, where FROM and TO are: {', '.join([s.value for s in Side])}.")):
    """
    Translate the current deck. If SIDE (format FROM-TO) is given, translates every note
    from FROM to TO, overwriting TO regardless of its current content.

    If SIDE is omitted, translates each note from whichever side is filled to whichever
    side is empty, skipping notes that already have text on both sides.
    """
    app.transform("translate", side=side)


@cli.command(context_settings=CTX_SETTINGS)
def transform(ctx: typer.Context, transformer: str = typer.Argument(help="Name of the transformer to use.")):
    """
    Transform the current deck using the specified TRANSFORMER.
    Additional keyword arguments can be passed to the transformer.
    """
    app.transform(transformer, **get_kwargs(ctx))


if __name__ == "__main__":
    cli()
