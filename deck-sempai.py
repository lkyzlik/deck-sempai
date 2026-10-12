import typer
from typing import Optional

from app.TuiApp import TuiApp
from Deck import Side
from Enums import GrammarRule, Model

CTX_SETTINGS = {"allow_extra_args": True, "ignore_unknown_options": True}


app = TuiApp()
cli = typer.Typer()


@cli.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """
    Manage Anki flashcard decks. If called with no command, runs an interactive menu
    to switch decks, add/transform cards, or create/delete decks.
    """
    if ctx.invoked_subcommand is None:
        app.tui()


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
    If no keyword arguments are provided, runs an interactive setup asking the same
    questions as 'create' (except the deck name) to update the metadata instead.
    """
    app.meta(**get_kwargs(ctx))


@cli.command()
def deck(name: Optional[str] = typer.Argument(None, help="Name of the deck to switch to. If omitted, runs an interactive picker.")):
    """
    Set the current deck to work with. If no NAME is provided, shows a list of all decks to
    choose from (the current one marked), with 'Create new' and 'Delete deck' options too.
    """
    app.deck(name)


@cli.command(context_settings=CTX_SETTINGS)
def create(ctx: typer.Context, name: Optional[str] = typer.Argument(None, help="Name of the new deck to create. If omitted, runs an interactive setup.")):
    """
    Create a new deck with the given NAME and switch to it. Additional metadata can be
    passed as space-separated key=value pairs, e.g. 'create MyDeck lang_front=da lang_back=en'.

    If NAME is omitted, runs an interactive setup that asks for the deck's name and,
    for language-learning decks, the languages on the front/back sides.
    """
    app.create(name, **get_kwargs(ctx))


@cli.command()
def delete(name: Optional[str] = typer.Argument(None, help="Name of the deck to delete. If omitted, runs an interactive picker.")):
    """
    Delete the deck with the given NAME, along with all its notes. If NAME is omitted,
    shows a list of all decks to choose from (the current one marked). Either way, asks
    for confirmation before deleting.
    """
    app.delete(name)


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
    until an empty line is entered.
    """
    app.add(front, back, model, tags)


@cli.command()
def show():
    """
    Show the current deck.
    """
    app.show()


@cli.command()
def status(integration: Optional[str] = typer.Argument(None, help="Name of a single integration to check (anki, ollama, ordnet). If omitted, shows all enabled ones.")):
    """
    Show the connection status of the integrations (anki, ollama, ordnet), with repair
    steps for any that are disconnected.

    If INTEGRATION is given, only that integration's status is shown.
    """
    app.status(integration)


@cli.command("add-sound")
def add_sound(side: Optional[str] = typer.Argument(None, help=f"Comma-separated sides of the card: {', '.join([s.value for s in Side])}. If omitted, runs an interactive picker.")):
    """
    Add sound to the specified SIDE(s) of the current deck. Multiple sides can be combined
    as a comma-separated list, e.g. 'front,back'. If SIDE is omitted, runs an interactive
    picker asking for the front side, back side, or both.
    """
    app.add_sound(side)


@cli.command("rm-sound")
def rm_sound(side: Optional[str] = typer.Argument(None, help=f"Comma-separated sides of the card: {', '.join([s.value for s in Side])}. If omitted, runs an interactive picker.")):
    """
    Remove sound from the specified SIDE(s) of the current deck. Multiple sides can be
    combined as a comma-separated list, e.g. 'front,back'. If SIDE is omitted, runs an
    interactive picker asking for the front side, back side, or both.
    """
    app.remove_sound(side)


@cli.command("add-grammar")
def add_grammar(rule: Optional[str] = typer.Argument(None, help=f"Comma-separated grammar help rules: {', '.join([g.value for g in GrammarRule])}. If omitted, runs an interactive picker."),
                 side: Optional[str] = typer.Argument(None, help=f"Comma-separated sides of the card: {', '.join([s.value for s in Side])}. If omitted, runs an interactive picker.")):
    """
    Add grammar help of the specified RULE(s) to the specified SIDE(s) of the current deck.
    Multiple rules or sides can each be combined as a comma-separated list, e.g.
    'noun_article,noun_plural' or 'front,back'. If RULE is omitted, runs an interactive
    picker allowing multiple rules to be selected. If SIDE is omitted, runs an interactive
    picker asking for the front side, back side, or both.
    """
    app.add_grammar(rule, side)


@cli.command()
def translate(side: Optional[str] = typer.Argument(None, help=f"Direction to translate: FROM:TO, where FROM and TO are: {', '.join([s.value for s in Side])}. If omitted, runs an interactive picker.")):
    """
    Translate the current deck. If SIDE (format FROM:TO) is given, translates every note
    from FROM to TO, overwriting TO regardless of its current content.

    If SIDE is omitted, runs an interactive picker to choose a direction, or an 'auto' mode
    that translates each note from whichever side is filled to whichever side is empty,
    skipping notes that already have text on both sides.
    """
    app.translate(side)


@cli.command(context_settings=CTX_SETTINGS)
def transform(ctx: typer.Context, transformer: str = typer.Argument(help="Name of the transformer to use.")):
    """
    Transform the current deck using the specified TRANSFORMER.
    Additional keyword arguments can be passed to the transformer.
    """
    app.transform(transformer, **get_kwargs(ctx))


if __name__ == "__main__":
    cli()
