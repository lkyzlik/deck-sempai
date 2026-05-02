from rich.console import Console
from rich.text import Text
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn

from interfaces.Logger import Logger, LoggerProgress


class RichLogger(Logger):
    def __init__(self, console: Console = Console()):
        self.console = console


    def print(self, message: str):
        self.console.print(message)


    def info(self, message: str):
        text = Text()
        text.append("Info: ", style="bold blue")
        text.append(message, style="green")
        self.console.print(text)


    def error(self, message: str):
        text = Text()
        text.append("Error: ", style="bold red")
        text.append(message, style="red")
        self.console.print(text)


    def warning(self, message: str):
        text = Text()
        text.append("Warning: ", style="bold yellow")
        text.append(message, style="yellow")
        self.console.print(text)


    def progress(self) -> LoggerProgress:
        return Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            console=self.console
        )