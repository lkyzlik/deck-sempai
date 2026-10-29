import shutil
import toml

from dacite import from_dict
from dataclasses import dataclass, field
from pathlib import Path
from platformdirs import user_config_dir


CONFIG_DIR = Path(user_config_dir("deck-sempai"))
DEFAULTS_DIR = Path(__file__).parent / "defaults"


# Returns the user's copy of a config file, creating it from the shipped default on first run.
def user_config_file(name: str) -> Path:
    path = CONFIG_DIR / name
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(DEFAULTS_DIR / name, path)
    return path


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
    def load(path: Path = None) -> "Config":
        with open(path or user_config_file("config.toml"), "r") as f:
            data = toml.load(f)
        return from_dict(Config, data)
