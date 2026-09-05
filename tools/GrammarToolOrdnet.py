from pathlib import Path

from bs4 import BeautifulSoup, Tag

from Enums import Language
from interfaces.OrdnetIntegration import OrdnetIntegration, OrdnetIntegrationError
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
        self.scraper = OrdnetIntegration()


    @staticmethod
    def _apply_form(word: str, form: str) -> str:
        # Ordnet's inflection table gives either a suffix ("-er") or, for irregular
        # words, the whole replacement form ("mænd").
        return word + form[1:] if form.startswith("-") else form


    def _find_entry(self, word: str) -> Tag:
        html = self.scraper.get_html(word)
        soup = BeautifulSoup(html, "html.parser")
        headwords = soup.find_all("h1", class_="modern-match")

        # A word already in its dictionary form matches a headword exactly (this also picks the
        # right sense when a page lists several homonyms of the same spelling). A verb searched
        # in a conjugated form won't match any headword directly, but ordnet.dk still resolves
        # the search to that verb's own page, so fall back to whichever entry it found.
        for headword in headwords:
            # The headword text is followed by a superscript homonym number (e.g. "arbejde <sup>1</sup>"),
            # so only look at the leading text node when matching.
            base = (headword.find(string=True, recursive=False) or "").strip()
            if base.lower() == word.lower():
                entry = headword.find_parent("div", class_="artikel")
                if entry:
                    return entry

        for headword in headwords:
            entry = headword.find_parent("div", class_="artikel")
            if entry:
                return entry

        raise OrdnetIntegrationError(f"Can't find a dictionary entry for {word!r}")


    def _get_headword(self, entry: Tag) -> str | None:
        headword = entry.find("h1", class_="modern-match")
        if not headword:
            return None
        return (headword.find(string=True, recursive=False) or "").strip() or None


    def _get_pos_key(self, entry: Tag) -> str | None:
        pos_span = entry.find(class_="part-of-speech")
        return pos_span.get("data-pos-key") if pos_span else None


    def _get_gender(self, entry: Tag) -> str | None:
        pos_span = entry.find(class_="part-of-speech")
        if not pos_span:
            return None
        gender_text = pos_span.parent.get_text(" ", strip=True)
        if "fælleskøn" in gender_text:
            return "fælleskøn"
        if "intetkøn" in gender_text:
            return "intetkøn"
        return None


    def _get_inflections(self, entry: Tag, word: str) -> list[str]:
        row = entry.find("div", id="id-boj")
        button = row.find("button", class_="kilde") if row else None
        if not button:
            raise OrdnetIntegrationError(f"Can't find inflection info for {word!r}")
        return [form.strip() for form in button.get_text(strip=True).split(",")]


    def _get_auxiliary_verb(self, entry: Tag) -> str:
        # Verbs are annotated per valency pattern (one per sense) with which auxiliary
        # verb(s) ("have" and/or "være") form the perfect tense with that pattern. Verbs
        # that always take "have" aren't annotated at all.
        auxiliaries = set()
        for label in entry.find_all("span", class_="stempelSmallNoBorder", string="HJÆLPEVERBUM"):
            text = label.parent.get_text(" ", strip=True).split("HJÆLPEVERBUM")[-1]
            if "have" in text:
                auxiliaries.add("have")
            if "være" in text:
                auxiliaries.add("være")

        # Verbs left unannotated always take "have"; verbs whose senses disagree
        # (e.g. "gå") can take either, so surface both rather than guessing.
        if not auxiliaries or auxiliaries == {"have"}:
            return "har"
        if auxiliaries == {"være"}:
            return "er"
        return "er/har"


    def pos(self, text: str) -> str:
        word = self.extract_word(text)["word"]
        try:
            entry = self._find_entry(word)
            pos_key = self._get_pos_key(entry)
        except OrdnetIntegrationError as e:
            raise GrammarToolError(str(e)) from e

        pos = self.POS_MAP.get(pos_key)
        if not pos:
            raise GrammarToolError(f"Can't classify the part of speech for {word!r}")
        return pos


    def noun_article(self, text: str) -> str:
        word = self.extract_word(text)["word"]
        try:
            entry = self._find_entry(word)
            gender = self._get_gender(entry)
        except OrdnetIntegrationError as e:
            raise GrammarToolError(str(e)) from e

        if gender == "fælleskøn":
            return "en"
        if gender == "intetkøn":
            return "et"
        raise GrammarToolError(f"Can't determine the article for {word!r}")


    def noun_plural_suffix(self, text: str, definite: bool = False) -> str:
        word = self.extract_word(text)["word"]
        try:
            entry = self._find_entry(word)
            forms = self._get_inflections(entry, word)
        except OrdnetIntegrationError as e:
            raise GrammarToolError(str(e)) from e

        if len(forms) < 3:
            raise GrammarToolError(f"Can't determine the plural for {word!r}")
        # Inflection order for nouns is: definite singular, indefinite plural, definite plural
        return forms[2] if definite else forms[1]


    def verb_infinitive(self, text: str) -> str:
        word = self.extract_word(text)["word"]
        try:
            entry = self._find_entry(word)
            infinitive = self._get_headword(entry)
        except OrdnetIntegrationError as e:
            raise GrammarToolError(str(e)) from e

        if not infinitive:
            raise GrammarToolError(f"Can't determine the infinitive for {word!r}")
        return f"{self.verb_infinitive_marker(text)} {infinitive}"


    def verb_tense(self, text: str, tense: str) -> str:
        word = self.extract_word(text)["word"]
        try:
            entry = self._find_entry(word)
            # Inflection suffixes are relative to the dictionary (infinitive) form, which can
            # differ from the word actually searched for (e.g. a conjugated form).
            infinitive = self._get_headword(entry) or word
            forms = self._get_inflections(entry, word)
        except OrdnetIntegrationError as e:
            raise GrammarToolError(str(e)) from e

        if len(forms) < 3:
            raise GrammarToolError(f"Can't determine the {tense} tense for {word!r}")
        # Inflection order for verbs is: present, past, past participle
        if tense == "past":
            return self._apply_form(infinitive, forms[1])
        if tense == "present_perfect":
            auxiliary = self._get_auxiliary_verb(entry)
            return f"{auxiliary} {self._apply_form(infinitive, forms[2])}"
        raise GrammarToolError(f"Unsupported tense {tense!r}")
