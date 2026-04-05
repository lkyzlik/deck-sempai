from rich.console import Console
from rich.text import Text

class Logger:
    def __init__(self):
        self.console = Console()


    def print(self, message: str | Text):
        self.console.print(message)


    def error(self, message: str | Text):
        text = Text()
        text.append("Error: ", style="bold red")
        text.append(message, style="red")
        self.console.print(text)


    def warning(self, message: str | Text):
        text = Text()
        text.append("Warning: ", style="bold yellow")
        text.append(message, style="yellow")
        self.console.print(text)