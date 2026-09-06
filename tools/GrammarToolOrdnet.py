from pathlib import Path

from bs4 import BeautifulSoup, Tag

from Enums import Language
from interfaces.OrdnetIntegration import OrdnetIntegration, OrdnetIntegrationError, OrdnetIntegrationDisabledError
from tools.GrammarTool import GrammarTool, GrammarToolError, GrammarToolDisabledError


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


    def _get_entry(self, text: str) -> Tag:
        # OrdnetIntegration.get_html() already resolves the text to the right dictionary
        # entry (picking the correct homonym when the text implies a part of speech), so
        # the returned HTML is just that one entry.
        html = self.scraper.get_html(text)
        return BeautifulSoup(html, "html.parser")


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
            entry = self._get_entry(text)
            pos_key = self._get_pos_key(entry)
        except OrdnetIntegrationDisabledError as e:
            raise GrammarToolDisabledError(str(e)) from e
        except OrdnetIntegrationError as e:
            raise GrammarToolError(str(e)) from e

        pos = self.POS_MAP.get(pos_key)
        if not pos:
            raise GrammarToolError(f"Can't classify the part of speech for {word!r}")
        return pos


    def noun_article(self, text: str) -> str:
        word = self.extract_word(text)["word"]
        try:
            entry = self._get_entry(text)
            gender = self._get_gender(entry)
        except OrdnetIntegrationDisabledError as e:
            raise GrammarToolDisabledError(str(e)) from e
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
            entry = self._get_entry(text)
            forms = self._get_inflections(entry, word)
        except OrdnetIntegrationDisabledError as e:
            raise GrammarToolDisabledError(str(e)) from e
        except OrdnetIntegrationError as e:
            raise GrammarToolError(str(e)) from e

        if len(forms) < 3:
            raise GrammarToolError(f"Can't determine the plural for {word!r}")
        # Inflection order for nouns is: definite singular, indefinite plural, definite plural
        return forms[2] if definite else forms[1]


    def verb_infinitive(self, text: str) -> str:
        word = self.extract_word(text)["word"]
        try:
            entry = self._get_entry(text)
            infinitive = self._get_headword(entry)
        except OrdnetIntegrationDisabledError as e:
            raise GrammarToolDisabledError(str(e)) from e
        except OrdnetIntegrationError as e:
            raise GrammarToolError(str(e)) from e

        if not infinitive:
            raise GrammarToolError(f"Can't determine the infinitive for {word!r}")
        return f"{self.verb_infinitive_marker(text)} {infinitive}"


    def verb_tense(self, text: str, tense: str) -> str:
        word = self.extract_word(text)["word"]
        try:
            entry = self._get_entry(text)
            # Inflection suffixes are relative to the dictionary (infinitive) form, which can
            # differ from the word actually searched for (e.g. a conjugated form).
            infinitive = self._get_headword(entry) or word
            forms = self._get_inflections(entry, word)
        except OrdnetIntegrationDisabledError as e:
            raise GrammarToolDisabledError(str(e)) from e
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
