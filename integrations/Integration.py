from typing import Protocol


class Integration(Protocol):
    name: str

    def enable(self, enable: bool):
        ...

    def configure(self, config: dict):
        ...

    def test_connection(self) -> bool:
        ...

    def status(self) -> str:
        ...

    def user_help(self) -> str:
        ...
