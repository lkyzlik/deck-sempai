from pathlib import Path

from Enums import Language
from integrations.OrdnetIntegration import OrdnetIntegration, OrdnetIntegrationError, OrdnetIntegrationDisabledError
from tools.grammar.GrammarTool import GrammarTool, GrammarToolError, GrammarToolDisabledError


class OrdnetGrammarTool(GrammarTool):
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

    POS_KEY_MAP = {pos: key for key, pos in POS_MAP.items()}


    def __init__(self, lang: Language, ordnet: OrdnetIntegration, media_dir: Path):
        super().__init__(lang)
        if lang != Language.DANISH:
            raise GrammarToolError(f"'ordnet.dk' grammar tool only supports Danish, not {lang}")
        self.scraper = ordnet


    @staticmethod
    def _apply_form(word: str, form: str) -> str:
        # Ordnet's inflection table gives either a suffix ("-er") or, for irregular
        # words, the whole replacement form ("mænd").
        return word + form[1:] if form.startswith("-") else form


    def _get_entry(self, text: str) -> dict:
        # Uses the cheap super().pos() heuristic, not self.pos(), to avoid recursing into _get_entry().
        word = self.extract_word(text)["word"]
        try:
            pos = super().pos(text)
        except GrammarToolError:
            pos = None
        try:
            return self.scraper.get_entry(word, pos=self.POS_KEY_MAP.get(pos))
        except OrdnetIntegrationDisabledError as e:
            raise GrammarToolDisabledError(str(e)) from e
        except OrdnetIntegrationError as e:
            raise GrammarToolError(str(e)) from e


    def pos(self, text: str) -> str:
        try:
            return super().pos(text)
        except GrammarToolError:
            pass

        word = self.extract_word(text)["word"]
        pos = self.POS_MAP.get(self._get_entry(text)["pos"])
        if not pos:
            raise GrammarToolError(f"Can't classify the part of speech for {word!r}")
        return pos


    def noun_article(self, text: str, definite: bool = False) -> str:
        if definite and not self.noun_has_definite_article():
            raise GrammarToolError(f"{self.lang} has no definite article")
        word = self.extract_word(text)["word"]
        gender = self._get_entry(text)["gender"]

        if gender == "fælleskøn":
            return "en"
        if gender == "intetkøn":
            return "et"
        raise GrammarToolError(f"Can't determine the article for {word!r}")


    def noun_plural_suffix(self, text: str, definite: bool = False) -> str:
        word = self.extract_word(text)["word"]
        forms = self._get_entry(text)["inflections"]

        if len(forms) < 3:
            raise GrammarToolError(f"Can't determine the plural for {word!r}")
        # Inflection order for nouns is: definite singular, indefinite plural, definite plural
        return forms[2] if definite else forms[1]


    def verb_infinitive(self, text: str) -> str:
        word = self.extract_word(text)["word"]
        infinitive = self._get_entry(text)["headword"]

        if not infinitive:
            raise GrammarToolError(f"Can't determine the infinitive for {word!r}")
        return f"{self.verb_infinitive_marker(text)} {infinitive}"


    def verb_tense(self, text: str, tense: str) -> str:
        word = self.extract_word(text)["word"]
        entry = self._get_entry(text)
        # Inflection suffixes are relative to the dictionary (infinitive) form, which can
        # differ from the word actually searched for (e.g. a conjugated form).
        infinitive = entry["headword"] or word
        forms = entry["inflections"]

        if len(forms) < 3:
            raise GrammarToolError(f"Can't determine the {tense} tense for {word!r}")
        # Inflection order for verbs is: present, past, past participle
        if tense == "past":
            return self._apply_form(infinitive, forms[1])
        if tense == "present_perfect":
            return f"{entry['auxiliary_verb']} {self._apply_form(infinitive, forms[2])}"
        raise GrammarToolError(f"Unsupported tense {tense!r}")
