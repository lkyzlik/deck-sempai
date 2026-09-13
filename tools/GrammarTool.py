import re

from typing import Protocol, runtime_checkable

from Enums import Language


class GrammarToolError(Exception):
    pass


class GrammarToolDisabledError(GrammarToolError):
    pass


class GrammarTool:
    # Articles and infinitive markers to strip from the front of a word, per language
    ARTICLES = {
        Language.DANISH: ("en", "et", "den", "det"),
        Language.ENGLISH_GB: ("a", "an", "the"),
        Language.ENGLISH_US: ("a", "an", "the"),
        Language.GERMAN_DE: ("der", "die", "das", "den", "dem", "des",
                              "ein", "eine", "einen", "einem", "einer", "eines"),
        Language.SPANISH_ES: ("el", "la", "los", "las", "un", "una", "unos", "unas"),
    }

    MARKERS = {
        Language.DANISH: ("at",),
        Language.ENGLISH_GB: ("to",),
        Language.ENGLISH_US: ("to",),
        Language.GERMAN_DE: ("zu",),
    }

    # Languages whose plural noun form differs between definite and indefinite (e.g. Danish
    # suffixes the article onto the noun); everyone else has a single plural form.
    LANGUAGES_WITH_DEFINITE_PLURAL = (Language.DANISH,)

    # Languages with a definite article as its own word (e.g. German 'der'/'die'/'das', Spanish
    # 'el'/'la'); Danish's definite article is a suffix on the noun instead, so it's excluded.
    LANGUAGES_WITH_DEFINITE_ARTICLE = (Language.ENGLISH_GB, Language.ENGLISH_US,
                                        Language.GERMAN_DE, Language.SPANISH_ES)

    def __init__(self, lang: Language) -> None:
        self.lang = lang

    def noun_has_definite_plural(self) -> bool:
        return self.lang in self.LANGUAGES_WITH_DEFINITE_PLURAL

    def noun_has_definite_article(self) -> bool:
        return self.lang in self.LANGUAGES_WITH_DEFINITE_ARTICLE

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

    def verb_infinitive_marker(self, text: str) -> str:
        # The infinitive marker is a fixed per-language word (e.g. "at" for Danish, "to" for
        # English), so unlike the other grammar rules this doesn't need a tool-specific lookup.
        markers = self.MARKERS.get(self.lang, ())
        if not markers:
            raise GrammarToolError(f"No infinitive marker configured for {self.lang}")
        return markers[0]

    def verb_infinitive(self, text: str) -> str:
        # A note's word isn't guaranteed to already be in infinitive form (e.g. it could be a
        # conjugated form), so resolving it to the infinitive needs a tool-specific lookup.
        raise NotImplementedError

    def pos(self, text: str) -> str:
        raise NotImplementedError

    def noun_article(self, text: str, definite: bool = False) -> str:
        raise NotImplementedError

    def noun_plural_suffix(self, text: str, definite: bool = False) -> str:
        raise NotImplementedError

    def verb_tense(self, text: str, tense: str) -> str:
        raise NotImplementedError
