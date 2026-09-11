from pathlib import Path

from Enums import Language
from integrations.OllamaIntegration import OllamaIntegration, OllamaIntegrationError, OllamaIntegrationDisabledError
from PromptLoader import PromptLoader, PromptPlaceholders
from tools.TranslateTool import TranslateTool, TranslateToolError, TranslateToolDisabledError


class TranslateToolOllama(TranslateTool):
    def __init__(self, lang_from: Language, lang_to: Language, ollama: OllamaIntegration, model: str = "gemma4",
                prompts_path: Path = "prompts.toml"):
        super().__init__(lang_from, lang_to)
        self.ollama = ollama
        self.model = model
        self.pl = PromptLoader(prompts_path)


    def translate(self, text: str) -> str:
        prompt = self.pl.get_prompt("translate", PromptPlaceholders(lang_from=self.lang_from, lang_to=self.lang_to))
        if not prompt:
            raise TranslateToolError("No 'translate' prompt found")

        messages = [
            {"role": "user", "content": prompt},
            {"role": "user", "content": text}
        ]
        try:
            return self.ollama.chat(self.model, messages, temperature=0)  # Deterministic output
        except OllamaIntegrationDisabledError as e:
            raise TranslateToolDisabledError(str(e)) from e
        except OllamaIntegrationError as e:
            raise TranslateToolError(f"AI request failed for {text!r}") from e
