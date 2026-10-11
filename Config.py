import toml

from dacite import from_dict
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AppConfig:
    deck_storage: str = "anki"
    frontend: str = "rich"
    log_level: str = "warning"


@dataclass
class AddCommandConfig:
    apply: list[str] = field(default_factory=list)


@dataclass
class CommandsConfig:
    sound: dict[str, str] = field(default_factory=dict)
    grammar: dict[str, str] = field(default_factory=dict)
    translate: dict[str, str] = field(default_factory=dict)
    add: AddCommandConfig = field(default_factory=AddCommandConfig)


@dataclass
class Config:
    app: AppConfig = field(default_factory=AppConfig)
    integrations: dict[str, dict] = field(default_factory=dict)
    commands: CommandsConfig = field(default_factory=CommandsConfig)

    @staticmethod
    def load(path: Path = Path("config.toml")) -> "Config":
        with open(path, "r") as f:
            data = toml.load(f)
        return from_dict(Config, data)
