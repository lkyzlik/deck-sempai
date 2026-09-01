import re

from pathlib import Path
from ollama import chat, ChatResponse, ResponseError

from Enums import Language
from interfaces.PromptLoader import PromptLoader, PromptPlaceholders
from tools.GrammarTool import GrammarTool, GrammarToolError


class GrammarToolOllama(GrammarTool):
    def __init__(self, lang: Language, model: str = "gemma4", prompts_path: Path = "prompts.toml"):
        super().__init__(lang)
        self.model = model
        self.pl = PromptLoader(prompts_path)


    def _ask(self, prompt_key: str, text: str, failure: str) -> str:
        prompt = self.pl.get_prompt(prompt_key, PromptPlaceholders(lang_from=self.lang))
        if not prompt:
            raise GrammarToolError(f"No {prompt_key!r} prompt found")

        try:
            messages = [
                {"role": "user", "content": prompt},
                {"role": "user", "content": text}
            ]
            response: ChatResponse = chat(self.model, messages=messages, think=False, keep_alive='10s')
            answer = response.message.content.strip().lower()
        except ResponseError as e:
            raise GrammarToolError(f"AI request failed for {text!r}") from e

        if answer == 'none':
            raise GrammarToolError(f"AI couldn't {failure} for {text!r}")

        return answer


    def extract_word(self, text: str) -> str:
        # Remove any text in braces (), [], <>, {}
        text = re.sub(r'[\(\[\{<][^)\]\}>]*[\)\]\}>]', '', text)
        # Remove Danish articles and infinitive markers
        text = re.sub(r'^(en|et|den|det|at)\s+', '', text, flags=re.IGNORECASE)
        # Remove numbers
        text = re.sub(r'\d+', '', text)
        # Remove punctuation
        text = re.sub(r'[^\w\s]', '', text)
        # Remove whitespace around
        text = text.strip()

        words = text.split()
        if len(words) != 1:
            raise GrammarToolError(f"Can't extract a single word from {text!r}")
        return words[0]


    def pos(self, text: str) -> str:
        return self._ask("pos", text, "classify the part of speech")


    def noun_article(self, text: str) -> str:
        return self._ask(f"noun.article.{self.lang.short()}", text, "determine the article")


    def noun_plural_suffix(self, text: str, definite: bool = False) -> str:
        key = "definite" if definite else "indefinite"
        return self._ask(f"noun.plural.{key}.{self.lang.short()}", text, f"determine the {key} plural")


    def verb_tense(self, text: str, tense: str) -> str:
        return self._ask(f"verb.tense.{tense}.{self.lang.short()}", text, f"determine the {tense} tense")
