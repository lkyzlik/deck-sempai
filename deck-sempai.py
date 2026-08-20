import typer
from typing import Optional

from App import App

# TODO: load from .toml file
CONFIG = {
    "load_importer": "anki",
    "save_exporter": "anki",
    "show_exporter": "rich",
}
CTX_SETTINGS = {"allow_extra_args": True, "ignore_unknown_options": True}


app = App(CONFIG)
cli = typer.Typer()
add_cli = typer.Typer()
rm_cli = typer.Typer()
cli.add_typer(add_cli, name="add")
cli.add_typer(rm_cli, name="rm")


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
def deck(name: Optional[str] = typer.Argument(None)):
    """
    Set the current deck to work with. If no NAME is provided, shows the current deck.
    """
    app.deck(name)


@cli.command(context_settings=CTX_SETTINGS)
def export(ctx: typer.Context, exporter: str):
    """
    Export the current deck using the specified EXPORTER.
    Additional keyword arguments can be passed to the exporter.
    """
    app.export(exporter, **get_kwargs(ctx))


# 'import' is a reserved keyword in Python, so we use 'import_' instead
@cli.command("import", context_settings=CTX_SETTINGS)
def import_(ctx: typer.Context, importer: str):
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


@add_cli.command("sound")
def add_sound(side: str = typer.Argument()):
    """
    Add sounds to the specified SIDE of the current deck using the sound manager.
    """
    app.transform("add-sound", side=side)


@add_cli.command("grammar")
def add_grammar(grammar_type: str = typer.Argument(), side: str = typer.Argument()):
    """
    Add grammar help of the specified TYPE to the specified SIDE of the current deck.
    """
    app.transform("add-grammar", grammar_type=grammar_type, side=side)


@rm_cli.command("sound")
def rm_sound(side: str = typer.Argument()):
    """
    Remove sounds from the specified SIDE of the current deck.
    """
    app.transform("remove-sound", side=side)


@cli.command(context_settings=CTX_SETTINGS)
def transform(ctx: typer.Context, transformer: str):
    """
    Transform the current deck using the specified TRANSFORMER.
    Additional keyword arguments can be passed to the transformer.
    """
    app.transform(transformer, **get_kwargs(ctx))


if __name__ == "__main__":
    cli()
