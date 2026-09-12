import toml

from dacite import from_dict
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AppConfig:
    deck_storage: str = "anki"


@dataclass
class Config:
    app: AppConfig = field(default_factory=AppConfig)
    integrations: dict[str, dict] = field(default_factory=dict)
    commands: dict[str, dict[str, str]] = field(default_factory=dict)

    @staticmethod
    def load(path: Path = Path("config.toml")) -> "Config":
        with open(path, "r") as f:
            data = toml.load(f)
        return from_dict(Config, data)
