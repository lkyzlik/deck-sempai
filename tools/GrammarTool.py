import re

from typing import Protocol, runtime_checkable

from Enums import Language


class GrammarToolError(Exception):
    pass


class GrammarTool:
    # Articles and infinitive markers to strip from the front of a word, per language
    ARTICLES = {
        Language.DANISH: ("en", "et", "den", "det"),
        Language.ENGLISH: ("a", "an", "the"),
    }

    MARKERS = {
        Language.DANISH: ("at",),
        Language.ENGLISH: ("to",),
    }

    def __init__(self, lang: Language) -> None:
        self.lang = lang

    def extract_word(self, text: str, keep_markers: bool = False, keep_articles: bool = False) -> str:
        # Remove any text in braces (), [], <>, {}
        text = re.sub(r'[\(\[\{<][^)\]\}>]*[\)\]\}>]', '', text)
        # Remove articles
        if not keep_articles:
            articles = self.ARTICLES.get(self.lang, ())
            if articles:
                text = re.sub(rf'^({"|".join(articles)})\s+', '', text, flags=re.IGNORECASE)
        # Remove infinitive markers
        if not keep_markers:
            markers = self.MARKERS.get(self.lang, ())
            if markers:
                text = re.sub(rf'^({"|".join(markers)})\s+', '', text, flags=re.IGNORECASE)
        # Remove punctuation
        text = re.sub(r'[^\w\s]', '', text)
        # Remove whitespace around
        return text.strip()

    def pos(self, text: str) -> str:
        raise NotImplementedError

    def noun_article(self, text: str) -> str:
        raise NotImplementedError

    def noun_plural_suffix(self, text: str, definite: bool = False) -> str:
        raise NotImplementedError

    def verb_tense(self, text: str, tense: str) -> str:
        raise NotImplementedError
