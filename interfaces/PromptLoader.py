import toml

from dataclasses import dataclass, asdict
from pathlib import Path

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
    def __init__(self, source: Path):
        with open(source, "r") as f:
            self.prompts = toml.load(f)


    def _get_template(self,key: str) -> str:
        prompts = self.prompts
        template = ""
        for part in key.split("."):
            if isinstance(prompts, str):
                raise ValueError(f"Prompt template not found for key: {key}")
            prompts = prompts.get(part, prompts.get("default"))
            if isinstance(prompts, str):
                template = template + prompts
            else:
                template = template + prompts.get(part, prompts.get('default', ''))
            
        return template


    def get_prompt(self, key: str, placeholders: PromptPlaceholders = PromptPlaceholders()) -> str:
        template = self._get_template(key)
        return template.format(**placeholders.to_dict())
    

    def get_subkeys(self, key: str, include_leafs: bool = True) -> list[str]:
        prompts = self.prompts
        for part in key.split("."):
            if part not in prompts:
                raise ValueError(f"Prompt template not found for key: {key}")
            prompts = prompts[part]
        if not isinstance(prompts, dict):
            raise ValueError(f"No subkeys found for key: {key}")
        if include_leafs:
            return list(prompts.keys())
        else:
            return [k for k, v in prompts.items() if isinstance(v, dict)]
