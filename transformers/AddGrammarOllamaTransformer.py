import re

from pathlib import Path
from ollama import chat, ChatResponse, ResponseError

from Deck import Deck, Note
from DeckOperator import DeckOpResult, DeckOpError, NoteOpResult
from Enums import Language, Side, GrammarRule

from interfaces.Logger import Logger
from interfaces.PromptLoader import PromptLoader, PromptPlaceholders
from transformers.Transformer import Transformer


class AddGrammarOllamaTransformer(Transformer):
    # Part of speech a word must be classified as for each grammar type;
    # words classified as anything else are left unchanged.
    REQUIRED_POS: dict[GrammarRule, str] = {
        GrammarRule.NOUN_ARTICLE: "noun",
        GrammarRule.NOUN_PLURAL: "noun",
        GrammarRule.VERB_TENSES: "verb",
    }

    # Template for the transformed note text. A [PLACEHOLDER] left unfilled (because that
    # grammar type wasn't requested or didn't apply to this word) is stripped out.
    RESULT_FORMAT = "[ARTICLE] [WORD] {[PLURAL]}{[TENSES]}"


    def __init__(self, logger: Logger, default_model: str = "gemma4", prompts_path: Path = "prompts.toml"):
        super().__init__(logger)
        self.default_model = default_model
        self.pl = PromptLoader(prompts_path)


    def _get_pos(self, word: str, model: str, placeholders: PromptPlaceholders) -> str | None:
        prompt = self.pl.get_prompt("pos", placeholders)
        if not prompt:
            self._warning(f"No 'pos' prompt found")
            return None
        try:
            messages = [
                {"role": "user", "content": prompt},
                {"role": "user", "content": word}
            ]
            response: ChatResponse = chat(model, messages=messages, think=False, keep_alive='10s')
            pos = response.message.content.strip().lower()
        except ResponseError:
            self._warning(f"AI part-of-speech classification failed {word!r}")
            return None

        if pos == 'none':
            self._warning(f"AI couldn't do part-of-speech classification for {word!r}")
            return None

        return pos


    def _get_noun_article(self, word: str, lang: Language, model: str, placeholders: PromptPlaceholders) -> str | None:
        prompt = self.pl.get_prompt(f"noun.article.{lang.short()}", placeholders)
        if not prompt:
            self._warning(f"No 'noun.article.{lang.short()}' prompt found")
            return None
        try:
            messages = [
                {"role": "user", "content": prompt},
                {"role": "user", "content": word}
            ]
            response: ChatResponse = chat(model, messages=messages, think=False, keep_alive='10s')
            article = response.message.content.strip().lower()
        except ResponseError:
            self._warning(f"AI grammar help failed for {word!r}")
            return None

        if article == 'none':
            self._warning(f"AI couldn't determine article for {word!r}")
            return None

        return article


    def _get_noun_plural(self, word: str, lang: Language, model: str, placeholders: PromptPlaceholders) -> str | None:
        # Indefinite plural suffix
        prompt = self.pl.get_prompt(f"noun.plural.indefinite.{lang.short()}", placeholders)
        if not prompt:
            self._warning(f"No 'noun.plural.indefinite.{lang.short()}' prompt found")
            return None
        try:
            messages = [
                {"role": "user", "content": prompt},
                {"role": "user", "content": word}
            ]
            response: ChatResponse = chat(model, messages=messages, think=False, keep_alive='10s')
            indef_plural = response.message.content.strip().lower()
        except ResponseError:
            self._warning(f"AI grammar help failed for {word!r}")
            return None

        # Definite plural suffix
        prompt = self.pl.get_prompt(f"noun.plural.definite.{lang.short()}", placeholders)
        if not prompt:
            self._warning(f"No 'noun.plural.definite.{lang.short()}' prompt found")
            return None
        try:
            messages = [
                {"role": "user", "content": prompt},
                {"role": "user", "content": word}
            ]
            response: ChatResponse = chat(model, messages=messages, think=False, keep_alive='10s')
            def_plural = response.message.content.strip().lower()
        except ResponseError:
            self._warning(f"AI grammar help failed for {word!r}")
            return None

        if indef_plural == 'none' or def_plural == 'none':
            self._warning(f"AI couldn't determine plural for {word!r}")
            return None

        return f"{indef_plural}, {def_plural}"


    def _get_verb_tenses(self, word: str, lang: Language, model: str, placeholders: PromptPlaceholders) -> str | None:
        # Past tense
        prompt = self.pl.get_prompt(f"verb.tense.past.{lang.short()}", placeholders)
        if not prompt:
            self._warning(f"No 'verb.tense.past.{lang.short()}' prompt found")
            return None
        try:
            messages = [
                {"role": "user", "content": prompt},
                {"role": "user", "content": word}
            ]
            response: ChatResponse = chat(model, messages=messages, think=False, keep_alive='10s')
            past = response.message.content.strip().lower()
        except ResponseError:
            self._warning(f"AI grammar help failed for {word!r}")
            return None

        # Present perfect tense
        prompt = self.pl.get_prompt(f"verb.tense.present_perfect.{lang.short()}", placeholders)
        if not prompt:
            self._warning(f"No 'verb.tense.present_perfect.{lang.short()}' prompt found")
            return None
        try:
            messages = [
                {"role": "user", "content": prompt},
                {"role": "user", "content": word}
            ]
            response: ChatResponse = chat(model, messages=messages, think=False, keep_alive='10s')
            present_perfect = response.message.content.strip().lower()
        except ResponseError:
            self._warning(f"AI grammar help failed for {word!r}")
            return None

        if past == 'none' or present_perfect == 'none':
            self._warning(f"AI couldn't determine tenses for {word!r}")
            return None

        return f"{past}, {present_perfect}"


    def _extract_word(self, text: str) -> str | None:
        # Remove any text in braces (), [], <>, {}
        text = re.sub(r'[\(\[\{<][^)\]\}>]*[\)\]\}>]', '', text)
        # Remove Danish articles and infinitive markers
        text = re.sub(r'^(en|et|den|det|at)\s+', '', text, flags=re.IGNORECASE)
        # Remove numbers
        text = re.sub(r'\d+', '', text)
        # Remove punctuation
        text = re.sub(r'[^\w\s]', '', text)
        # Remove whitespace around
        text = text.strip()
        # Fail if there is more than one word left
        if len(text.split()) != 1:
            return None
        # Return the cleaned word
        return text.split()[0]


    def _fill_result_format(self, values: dict[str, str]) -> str:
        text = re.sub(r'\[(\w+)\]', lambda m: values.get(m.group(1)) or '', self.RESULT_FORMAT)
        text = re.sub(r'\{\s*\}', '', text)       # drop braces left empty by unused suffixes
        return re.sub(r'\s+', ' ', text).strip()  # collapse whitespace left by unused parts


    def _transform_note(self, note: Note, side: Side, lang: Language,
                        grammar_rules: list[GrammarRule], model: str) -> NoteOpResult:
        field = note.get_field(side)
        placeholders = PromptPlaceholders(lang_from=lang)

        # Extract the word to be transformed
        word = self._extract_word(field.text)
        if not word:
            self._warning(f"Can't extract word from {field.get_text_oneline()!r}")
            return NoteOpResult(success=False)

        # Classify the word once, then keep only the requested types that match its part of speech
        pos = self._get_pos(word, model, placeholders)
        applicable_types = [gt for gt in grammar_rules if self.REQUIRED_POS[gt] == pos]
        if not applicable_types:
            self._info(f"Skipping {field.get_text_oneline()!r}: Doesn't match any requested grammar type")
            return NoteOpResult(success=True)

        # Fetch the grammar help for every applicable type and fill it into RESULT_FORMAT.
        # Each entry maps a grammar type to its (placeholder name, value-fetching method).
        handlers: dict[GrammarRule, tuple[str, callable]] = {
            GrammarRule.NOUN_ARTICLE: ("ARTICLE", self._get_noun_article),
            GrammarRule.NOUN_PLURAL: ("PLURAL", self._get_noun_plural),
            GrammarRule.VERB_TENSES: ("TENSES", self._get_verb_tenses),
        }
        values = {"WORD": word}
        for grammar_rule in applicable_types:
            placeholder, get_value = handlers[grammar_rule]
            value = get_value(word, lang, model, placeholders)
            if not value:
                return NoteOpResult(success=False)
            values[placeholder] = value

        field.text = self._fill_result_format(values)
        return NoteOpResult(success=True)


    def _transform_deck(self, deck: Deck, side: Side, lang: Language,
                        grammar_rules: list[GrammarRule], model: str) -> DeckOpResult:
        with self.logger.progress() as prog:
            task = prog.add_task("Adding grammar help...", total=len(deck.notes))

            results: list[NoteOpResult] = []
            for note in deck.notes:
                result = self._transform_note(note, side, lang, grammar_rules, model or self.default_model)
                results.append(result)
                prog.update(task, advance=1)

        return DeckOpResult(results, op_title="Added grammar help (AI)")


    def transform_deck(self, deck: Deck, side: str = Side.FRONT.value, lang: str = None,
                       grammar_rule: str = None, model: str = None) -> DeckOpResult:
        try:
            side = Side(side)
        except ValueError:
            raise DeckOpError(self, "Invalid argument: side, supported: " +
                                    ', '.join([s.value for s in Side]))

        if not lang:
            raise DeckOpError(self, "Missing argument: lang")
        try:
            lang = Language(lang)
        except ValueError:
            raise DeckOpError(self, "Invalid argument: lang, supported: " +
                                    ', '.join([l.value for l in Language]))

        if not grammar_rule:
            raise DeckOpError(self, "Missing argument: grammar_rule, supported: " +
                                    ', '.join([g.value for g in GrammarRule]))
        try:
            grammar_rules = [GrammarRule(gt.strip()) for gt in grammar_rule.split(",")]
        except ValueError:
            raise DeckOpError(self, "Invalid argument: grammar_rule, supported (comma-separated): " +
                                    ', '.join([g.value for g in GrammarRule]))

        return self._transform_deck(deck, side, lang, grammar_rules, model)
