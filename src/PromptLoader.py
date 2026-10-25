import toml

from dataclasses import dataclass
from pathlib import Path

from Config import user_config_file
from Enums import Language


@dataclass
class PromptPlaceholders:
    lang_from: Language = None
    lang_to: Language = None

    def to_dict(self):
        return {
            "lang_from": self.lang_from.value if self.lang_from else "(detect language)",
            "lang_to": self.lang_to.value if self.lang_to else "(detect language)",
        }


class PromptLoader:
    def __init__(self, source: Path = None):
        with open(source or user_config_file("prompts.toml"), "r") as f:
            self.prompts = toml.load(f)


    def _get_template(self, key: str) -> str | None:
        prompts = self.prompts
        for part in key.split("."):
            prompts = prompts.get(part)
            if prompts is None:
                return None

        if isinstance(prompts, str):
            return prompts
                
        return None


    def get_prompt(self, key: str, placeholders: PromptPlaceholders = PromptPlaceholders()) -> str | None:
        template = self._get_template(key)
        return template.format(**placeholders.to_dict()) if template else None
