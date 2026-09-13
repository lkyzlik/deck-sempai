from pathlib import Path

from Enums import Language
from integrations.OllamaIntegration import OllamaIntegration, OllamaIntegrationError, OllamaIntegrationDisabledError
from PromptLoader import PromptLoader, PromptPlaceholders
from tools.GrammarTool import GrammarTool, GrammarToolError, GrammarToolDisabledError


class GrammarToolOllama(GrammarTool):
    def __init__(self, lang: Language, ollama: OllamaIntegration, model: str = None,
                prompts_path: Path = "prompts.toml"):
        super().__init__(lang)
        self.ollama = ollama
        self.model = model
        self.pl = PromptLoader(prompts_path)


    def _ask(self, prompt_key: str, word: str, failure: str) -> str:
        prompt = self.pl.get_prompt(prompt_key, PromptPlaceholders(lang_from=self.lang))
        if not prompt:
            raise GrammarToolError(f"No {prompt_key!r} prompt found")

        messages = [
            {"role": "user", "content": prompt},
            {"role": "user", "content": word}
        ]
        chat_kwargs = {"model": self.model} if self.model else {}
        try:
            answer = self.ollama.chat(messages, temperature=0, **chat_kwargs).lower()  # Deterministic output
        except OllamaIntegrationDisabledError as e:
            raise GrammarToolDisabledError(str(e)) from e
        except OllamaIntegrationError as e:
            raise GrammarToolError(f"AI request failed for {word!r}") from e

        if answer == 'none':
            raise GrammarToolError(f"AI couldn't {failure} for {word!r}")

        return answer


    def _word_with(self, text: str, keep_articles: bool = False, keep_markers: bool = False) -> str:
        # Extra context (an existing article or infinitive marker) can help the AI, so
        # re-attach whichever of them the caller wants kept in front of the bare word.
        result = self.extract_word(text)
        parts = []
        if keep_articles:
            parts.append(result["articles"])
        if keep_markers:
            parts.append(result["markers"])
        parts.append(result["word"])
        return " ".join(filter(None, parts))


    def pos(self, text: str) -> str:
        word = self._word_with(text, keep_articles=True, keep_markers=True)
        try:
            return super().pos(text)
        except GrammarToolDisabledError:
            raise
        except GrammarToolError:
            return self._ask("pos", word, "classify the part of speech")


    def noun_article(self, text: str, definite: bool = False) -> str:
        if definite and not self.noun_has_definite_article():
            raise GrammarToolError(f"{self.lang} has no definite article")
        word = self._word_with(text, keep_articles=True)
        key = "definite" if definite else "indefinite"
        return self._ask(f"noun.article.{key}.{self.lang.short()}", word, f"determine the {key} article")


    def noun_plural_suffix(self, text: str, definite: bool = False) -> str:
        word = self._word_with(text, keep_articles=True)
        if self.noun_has_definite_plural():
            key = "definite" if definite else "indefinite"
            return self._ask(f"noun.plural.{key}.{self.lang.short()}", word, f"determine the {key} plural")
        return self._ask(f"noun.plural.{self.lang.short()}", word, "determine the plural")


    def verb_tense(self, text: str, tense: str) -> str:
        word = self._word_with(text, keep_markers=True)
        return self._ask(f"verb.tense.{tense}.{self.lang.short()}", word, f"determine the {tense} tense")


    def verb_infinitive(self, text: str) -> str:
        word = self._word_with(text, keep_markers=True)
        infinitive = self._ask(f"verb.infinitive.{self.lang.short()}", word, "determine the infinitive form")
        return f"{self.verb_infinitive_marker(text)} {infinitive}"
