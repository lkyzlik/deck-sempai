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

    def extract_word(self, text: str) -> dict[str, str | None]:
        # Remove any text in braces (), [], <>, {}
        text = re.sub(r'[\(\[\{<][^)\]\}>]*[\)\]\}>]', '', text).strip()

        # Pull off a leading article, if any
        article = None
        articles = self.ARTICLES.get(self.lang, ())
        if articles:
            match = re.match(rf'^({"|".join(articles)})\s+', text, flags=re.IGNORECASE)
            if match:
                article = match.group(1)
                text = text[match.end():]

        # Pull off a leading infinitive marker, if any
        marker = None
        markers = self.MARKERS.get(self.lang, ())
        if markers:
            match = re.match(rf'^({"|".join(markers)})\s+', text, flags=re.IGNORECASE)
            if match:
                marker = match.group(1)
                text = text[match.end():]

        # Remove punctuation and surrounding whitespace from what's left
        word = re.sub(r'[^\w\s]', '', text).strip()

        return {"word": word, "articles": article, "markers": marker}

    def pos(self, text: str) -> str:
        raise NotImplementedError

    def noun_article(self, text: str) -> str:
        raise NotImplementedError

    def noun_plural_suffix(self, text: str, definite: bool = False) -> str:
        raise NotImplementedError

    def verb_tense(self, text: str, tense: str) -> str:
        raise NotImplementedError
