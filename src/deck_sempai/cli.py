import typer
from typing import Optional

from deck_sempai.TuiApp import TuiApp
from deck_sempai.Deck import Side
from deck_sempai.Enums import GrammarRule, Model

CTX_SETTINGS = {"allow_extra_args": True, "ignore_unknown_options": True}


app = TuiApp()
cli = typer.Typer()


@cli.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """
    Manage flashcard decks. Runs an interactive TUI if no command is provided.

    To get started:
    1. Create a new deck using the 'create' command.
    2. Add notes to the deck using the 'add' command.
    3. See the current deck using the 'show' command.
    4. Get detailed command help using the '--help' option with any command.
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


@cli.command()
def add(front: Optional[str] = typer.Argument(None, help="Front text of the new note. Filled in via translation if omitted (requires --back)."),
        back: Optional[str] = typer.Option(None, "--back", "-b", help="Back text of the new note. Filled in via translation if omitted (requires FRONT)."),
        model: Optional[str] = typer.Option(None, "--model", "-m", help=f"Note model: {', '.join([m.value for m in Model])}"),
        tags: Optional[str] = typer.Option(None, "--tags", "-t", help="Comma-separated tags to add to the note.")):
    """
    Add a new note to the current deck and run configured transfomrations on it.
    """
    app.add(front, back, model, tags)


@cli.command("add-grammar")
def add_grammar(rule: Optional[str] = typer.Argument(None, help=f"Comma-separated grammar help rules: {', '.join([g.value for g in GrammarRule])}. If omitted, runs an interactive picker."),
                 side: Optional[str] = typer.Argument(None, help=f"Comma-separated sides of the card: {', '.join([s.value for s in Side])}. If omitted, runs an interactive picker.")):
    """
    Add grammar help, such as noun articles or plurals, to the notes of the current deck.
    """
    app.add_grammar(rule, side)


@cli.command("add-sound")
def add_sound(side: Optional[str] = typer.Argument(None, help=f"Comma-separated sides of the card: {', '.join([s.value for s in Side])}. If omitted, runs an interactive picker.")):
    """
    Add pronunciation sound to the notes of the current deck.
    """
    app.add_sound(side)


@cli.command(context_settings=CTX_SETTINGS)
def create(ctx: typer.Context, name: Optional[str] = typer.Argument(None, help="Name of the new deck to create. If omitted, runs an interactive setup.")):
    """
    Create a new deck and switch to it.
    """
    app.create(name, **get_kwargs(ctx))


@cli.command()
def deck(name: Optional[str] = typer.Argument(None, help="Name of the deck to switch to. If omitted, runs an interactive picker.")):
    """
    Switch the deck to work with.
    """
    app.deck(name)


@cli.command()
def delete(name: Optional[str] = typer.Argument(None, help="Name of the deck to delete. If omitted, runs an interactive picker.")):
    """
    Delete a deck along with all its notes.
    """
    app.delete(name)


@cli.command(context_settings=CTX_SETTINGS)
def export(ctx: typer.Context, exporter: str = typer.Argument(help="Name of the exporter to use.")):
    """
    Export the current deck to an external destination, such as Anki.
    """
    app.export(exporter, **get_kwargs(ctx))


# 'import' is a reserved keyword in Python, so we use 'import_' instead
@cli.command("import", context_settings=CTX_SETTINGS)
def import_(ctx: typer.Context, importer: str = typer.Argument(help="Name of the importer to use.")):
    """
    Import notes into the current deck from an external source, such as Anki.
    """
    app.import_(importer, **get_kwargs(ctx))


@cli.command(context_settings=CTX_SETTINGS)
def meta(ctx: typer.Context):
    """
    Update the current deck's metadata, such as the languages of its front and back sides.
    """
    app.meta(**get_kwargs(ctx))


@cli.command("rm-sound")
def rm_sound(side: Optional[str] = typer.Argument(None, help=f"Comma-separated sides of the card: {', '.join([s.value for s in Side])}. If omitted, runs an interactive picker.")):
    """
    Remove sound from the notes of the current deck.
    """
    app.remove_sound(side)


@cli.command()
def show(only_meta: bool = typer.Option(False, "--only-meta", help="Show only the deck name and metadata, without notes.")):
    """
    Show the current deck.
    """
    app.show(only_meta)


@cli.command()
def status(integration: Optional[str] = typer.Argument(None, help="Name of a single integration to check (anki, ollama, ordnet). If omitted, shows all enabled ones.")):
    """
    Show the connection status of the external integrations, with repair steps for any that are disconnected.
    """
    app.status(integration)


@cli.command(context_settings=CTX_SETTINGS)
def transform(ctx: typer.Context, transformer: str = typer.Argument(help="Name of the transformer to use.")):
    """
    Transform the notes of the current deck.
    """
    app.transform(transformer, **get_kwargs(ctx))


@cli.command()
def translate(side: Optional[str] = typer.Argument(None, help=f"Direction to translate: FROM:TO, where FROM and TO are: {', '.join([s.value for s in Side])}. If omitted, runs an interactive picker.")):
    """
    Translate the notes of the current deck from one side to the other.
    """
    app.translate(side)


if __name__ == "__main__":
    cli()
