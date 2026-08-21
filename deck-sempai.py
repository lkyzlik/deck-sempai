import typer
from typing import Optional

from App import App
from Deck import Side

# TODO: load from .toml file
CONFIG = {
    "load_importer": "anki",
    "save_exporter": "anki",
    "show_exporter": "rich",
}
CTX_SETTINGS = {"allow_extra_args": True, "ignore_unknown_options": True}


app = App(CONFIG)
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
def grammar(grammar_type: str = typer.Argument(help="Type of grammar help."),
            side: str = typer.Argument(help=f"Side of the card: {', '.join([s.value for s in Side])}")):
    """
    Add grammar help of the specified TYPE to the specified SIDE of the current deck.
    """
    app.transform("add-grammar", grammar_type=grammar_type, side=side)


@cli.command(context_settings=CTX_SETTINGS)
def transform(ctx: typer.Context, transformer: str = typer.Argument(help="Name of the transformer to use.")):
    """
    Transform the current deck using the specified TRANSFORMER.
    Additional keyword arguments can be passed to the transformer.
    """
    app.transform(transformer, **get_kwargs(ctx))


if __name__ == "__main__":
    cli()
