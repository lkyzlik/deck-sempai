from pathlib import Path
from ollama import chat, ChatResponse, ResponseError

from Enums import Language
from interfaces.PromptLoader import PromptLoader, PromptPlaceholders
from tools.TranslateTool import TranslateTool, TranslateToolError


class TranslateToolOllama(TranslateTool):
    def __init__(self, lang_from: Language, lang_to: Language, model: str = "gemma4",
                prompts_path: Path = "prompts.toml"):
        super().__init__(lang_from, lang_to)
        self.model = model
        self.pl = PromptLoader(prompts_path)


    def translate(self, text: str) -> str:
        prompt = self.pl.get_prompt("translate", PromptPlaceholders(lang_from=self.lang_from, lang_to=self.lang_to))
        if not prompt:
            raise TranslateToolError("No 'translate' prompt found")

        try:
            messages = [
                {"role": "user", "content": prompt},
                {"role": "user", "content": text}
            ]
            options = {"temperature": 0}  # Deterministic output
            response: ChatResponse = chat(self.model, messages=messages, think=False, keep_alive='10s', options=options)
            return response.message.content.strip()
        except ResponseError as e:
            raise TranslateToolError(f"AI request failed for {text!r}") from e
