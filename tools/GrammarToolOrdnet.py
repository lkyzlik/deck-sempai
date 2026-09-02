from pathlib import Path

from Enums import Language
from interfaces.OrdnetScraper import OrdnetScraper, OrdnetScraperError
from tools.GrammarTool import GrammarTool, GrammarToolError


class GrammarToolOrdnet(GrammarTool):
    # Maps ordnet.dk's part-of-speech abbreviations to the vocabulary used elsewhere in the app
    # (see AddGrammarTransformer.REQUIRED_POS and the `pos` prompt in prompts.toml).
    POS_MAP = {
        "sb.": "noun",
        "vb.": "verb",
        "adj.": "adjective",
        "adv.": "adverb",
        "pron.": "pronoun",
        "præp.": "preposition",
        "konj.": "conjunction",
        "interj.": "interjection",
    }


    def __init__(self, lang: Language, media_dir: Path):
        super().__init__(lang)
        if lang != Language.DANISH:
            raise GrammarToolError(f"'ordnet.dk' grammar tool only supports Danish, not {lang}")
        self.scraper = OrdnetScraper(media_dir)


    @staticmethod
    def _apply_form(word: str, form: str) -> str:
        # Ordnet's inflection table gives either a suffix ("-er") or, for irregular
        # words, the whole replacement form ("mænd").
        return word + form[1:] if form.startswith("-") else form


    def _auxiliary_verb(self, text: str) -> str:
        word = self.extract_word(text)
        try:
            auxiliaries = self.scraper.get_auxiliary_verbs(word)
        except OrdnetScraperError as e:
            raise GrammarToolError(str(e)) from e

        # Verbs left unannotated always take "have"; verbs whose senses disagree
        # (e.g. "gå") can take either, so surface both rather than guessing.
        if not auxiliaries or auxiliaries == {"have"}:
            return "har"
        if auxiliaries == {"være"}:
            return "er"
        return "er/har"


    def pos(self, text: str) -> str:
        word = self.extract_word(text)
        try:
            pos_key = self.scraper.get_pos_key(word)
        except OrdnetScraperError as e:
            raise GrammarToolError(str(e)) from e

        pos = self.POS_MAP.get(pos_key)
        if not pos:
            raise GrammarToolError(f"Can't classify the part of speech for {word!r}")
        return pos


    def noun_article(self, text: str) -> str:
        word = self.extract_word(text)
        try:
            gender = self.scraper.get_gender(word)
        except OrdnetScraperError as e:
            raise GrammarToolError(str(e)) from e

        if gender == "fælleskøn":
            return "en"
        if gender == "intetkøn":
            return "et"
        raise GrammarToolError(f"Can't determine the article for {word!r}")


    def noun_plural_suffix(self, text: str, definite: bool = False) -> str:
        word = self.extract_word(text)
        try:
            forms = self.scraper.get_inflections(word)
        except OrdnetScraperError as e:
            raise GrammarToolError(str(e)) from e

        if len(forms) < 3:
            raise GrammarToolError(f"Can't determine the plural for {word!r}")
        # Inflection order for nouns is: definite singular, indefinite plural, definite plural
        return forms[2] if definite else forms[1]


    def verb_tense(self, text: str, tense: str) -> str:
        word = self.extract_word(text)
        try:
            forms = self.scraper.get_inflections(word)
        except OrdnetScraperError as e:
            raise GrammarToolError(str(e)) from e

        if len(forms) < 3:
            raise GrammarToolError(f"Can't determine the {tense} tense for {word!r}")
        # Inflection order for verbs is: present, past, past participle
        if tense == "past":
            return self._apply_form(word, forms[1])
        if tense == "present_perfect":
            return f"{self._auxiliary_verb(word)} {self._apply_form(word, forms[2])}"
        raise GrammarToolError(f"Unsupported tense {tense!r}")
