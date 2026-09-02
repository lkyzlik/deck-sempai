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


    def _ask(self, prompt_key: str, word: str, failure: str) -> str:
        prompt = self.pl.get_prompt(prompt_key, PromptPlaceholders(lang_from=self.lang))
        if not prompt:
            raise GrammarToolError(f"No {prompt_key!r} prompt found")

        try:
            messages = [
                {"role": "user", "content": prompt},
                {"role": "user", "content": word}
            ]
            response: ChatResponse = chat(self.model, messages=messages, think=False, keep_alive='10s')
            answer = response.message.content.strip().lower()
        except ResponseError as e:
            raise GrammarToolError(f"AI request failed for {word!r}") from e

        if answer == 'none':
            raise GrammarToolError(f"AI couldn't {failure} for {word!r}")

        return answer


    def pos(self, text: str) -> str:
        word = self.extract_word(text, keep_markers=True, keep_articles=True)
        return self._ask("pos", word, "classify the part of speech")


    def noun_article(self, text: str) -> str:
        word = self.extract_word(text, keep_articles=True)
        return self._ask(f"noun.article.{self.lang.short()}", word, "determine the article")


    def noun_plural_suffix(self, text: str, definite: bool = False) -> str:
        key = "definite" if definite else "indefinite"
        word = self.extract_word(text, keep_articles=True)
        return self._ask(f"noun.plural.{key}.{self.lang.short()}", word, f"determine the {key} plural")


    def verb_tense(self, text: str, tense: str) -> str:
        word = self.extract_word(text, keep_markers=True)
        return self._ask(f"verb.tense.{tense}.{self.lang.short()}", word, f"determine the {tense} tense")
