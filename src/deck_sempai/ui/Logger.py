from typing import Protocol


class LoggerProgress(Protocol):
    def __enter__(self) -> 'LoggerProgress':
        ...

    def __exit__(self, exc_type, exc_val, exc_tb):
        ...

    def add_task(self, description: str, total: int) -> int:
        ...

    def update(self, task_id: int, advance: int = 0, description: str = None):
        ...


class Logger(Protocol):
    def print(self, message: str):
        ...

    def info(self, message: str):
        ...

    def warning(self, message: str):
        ...

    def error(self, message: str):
        ...

    def progress(self) -> LoggerProgress:
        ...