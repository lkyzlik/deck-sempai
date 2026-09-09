from pathlib import Path

from Enums import Language
from integrations.OllamaIntegration import OllamaIntegration, OllamaIntegrationError, OllamaIntegrationDisabledError
from interfaces.PromptLoader import PromptLoader, PromptPlaceholders
from tools.GrammarTool import GrammarTool, GrammarToolError, GrammarToolDisabledError


class GrammarToolOllama(GrammarTool):
    def __init__(self, lang: Language, ollama: OllamaIntegration, model: str = "gemma4",
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
        try:
            answer = self.ollama.chat(self.model, messages, temperature=0).lower()  # Deterministic output
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
        return self._ask("pos", word, "classify the part of speech")


    def noun_article(self, text: str) -> str:
        word = self._word_with(text, keep_articles=True)
        return self._ask(f"noun.article.{self.lang.short()}", word, "determine the article")


    def noun_plural_suffix(self, text: str, definite: bool = False) -> str:
        key = "definite" if definite else "indefinite"
        word = self._word_with(text, keep_articles=True)
        return self._ask(f"noun.plural.{key}.{self.lang.short()}", word, f"determine the {key} plural")


    def verb_tense(self, text: str, tense: str) -> str:
        word = self._word_with(text, keep_markers=True)
        return self._ask(f"verb.tense.{tense}.{self.lang.short()}", word, f"determine the {tense} tense")


    def verb_infinitive(self, text: str) -> str:
        word = self._word_with(text, keep_markers=True)
        infinitive = self._ask(f"verb.infinitive.{self.lang.short()}", word, "determine the infinitive form")
        return f"{self.verb_infinitive_marker(text)} {infinitive}"
