import re

from Deck import Deck, Note
from DeckOperator import DeckOpResult, DeckOpError, NoteOpResult
from Enums import Side, GrammarRule

from ui.Logger import Logger
from tools.GrammarTool import GrammarTool, GrammarToolError, GrammarToolDisabledError
from transformers.Transformer import Transformer


class AddGrammarTransformer(Transformer):
    # Part of speech a word must be classified as for each grammar type;
    # words classified as anything else are left unchanged.
    REQUIRED_POS: dict[GrammarRule, str] = {
        GrammarRule.NOUN_ARTICLE: "noun",
        GrammarRule.NOUN_PLURAL: "noun",
        GrammarRule.VERB_TENSES: "verb",
        GrammarRule.VERB_INFINITIVE: "verb",
    }

    # Template for the transformed note text. A [PLACEHOLDER] left unfilled (because that
    # grammar type wasn't requested or didn't apply to this word) is stripped out.
    RESULT_FORMAT = "[ARTICLE] [WORD] {[PLURAL]}{[TENSES]}"


    def __init__(self, logger: Logger, tool: GrammarTool):
        super().__init__(logger)
        self.tool = tool


    def _get_verb_tenses(self, word: str) -> str:
        past = self.tool.verb_tense(word, "past")
        present_perfect = self.tool.verb_tense(word, "present_perfect")
        return f"{past}, {present_perfect}"


    def _get_noun_plural(self, word: str) -> str:
        if not self.tool.noun_has_definite_plural():
            return f"{self.tool.noun_plural_suffix(word)}"
        indefinite = self.tool.noun_plural_suffix(word)
        definite = self.tool.noun_plural_suffix(word, definite=True)
        return f"{indefinite}, {definite}"


    def _get_noun_article(self, word: str) -> str:
        return self.tool.noun_article(word, definite=self.tool.noun_has_definite_article())


    def _fill_result_format(self, values: dict[str, str]) -> str:
        text = re.sub(r'\[(\w+)\]', lambda m: values.get(m.group(1)) or '', self.RESULT_FORMAT)
        text = re.sub(r'\{\s*\}', '', text)       # drop braces left empty by unused suffixes
        return re.sub(r'\s+', ' ', text).strip()  # collapse whitespace left by unused parts


    def _transform_note(self, note: Note, side: Side, grammar_rules: list[GrammarRule]) -> NoteOpResult:
        field = note.get_field(side)

        # Classify the word once, then keep only the requested rules that match its part of speech
        try:
            pos = self.tool.pos(field.text)
        except GrammarToolDisabledError as e:
            raise DeckOpError(self, str(e)) from e
        except GrammarToolError as e:
            self._warning(str(e))
            pos = None
        applicable_rules = [gr for gr in grammar_rules if self.REQUIRED_POS[gr] == pos]
        if not applicable_rules:
            self._info(f"Skipping {field.get_text_oneline()!r}: Doesn't match any requested grammar type")
            return NoteOpResult(success=True)

        # Fetch the grammar help for every applicable rule and fill it into RESULT_FORMAT.
        # Each entry maps a grammar rule to its (placeholder name, value-fetching method).
        handlers: dict[GrammarRule, tuple[str, callable]] = {
            GrammarRule.NOUN_ARTICLE: ("ARTICLE", self._get_noun_article),
            GrammarRule.NOUN_PLURAL: ("PLURAL", self._get_noun_plural),
            GrammarRule.VERB_TENSES: ("TENSES", self._get_verb_tenses),
            GrammarRule.VERB_INFINITIVE: ("WORD", self.tool.verb_infinitive),
        }
        values = {"WORD": self.tool.extract_word(field.text)["word"]}
        for grammar_rule in applicable_rules:
            placeholder, get_value = handlers[grammar_rule]
            try:
                values[placeholder] = get_value(field.text)
            except GrammarToolDisabledError as e:
                raise DeckOpError(self, str(e)) from e
            except GrammarToolError as e:
                self._warning(str(e))
                return NoteOpResult(success=False)

        field.text = self._fill_result_format(values)
        return NoteOpResult(success=True)


    def _transform_deck(self, deck: Deck, side: Side, grammar_rules: list[GrammarRule]) -> DeckOpResult:
        with self.logger.progress() as prog:
            task = prog.add_task("Adding grammar help...", total=len(deck.notes))

            results: list[NoteOpResult] = []
            for note in deck.notes:
                result = self._transform_note(note, side, grammar_rules)
                results.append(result)
                prog.update(task, advance=1)

        return DeckOpResult(results, op_title="Added grammar help (AI)")


    def transform_deck(self, deck: Deck, side: str = Side.FRONT.value, rule: str = None) -> DeckOpResult:
        try:
            side = Side(side)
        except ValueError:
            raise DeckOpError(self, "Invalid argument: side, supported: " +
                                    ', '.join([s.value for s in Side]))

        if not rule:
            grammar_rules = list(GrammarRule)
        else:
            try:
                grammar_rules = [GrammarRule(gr.strip()) for gr in rule.split(",")]
            except ValueError:
                raise DeckOpError(self, "Invalid argument: rule, supported (comma-separated): " +
                                        ', '.join([g.value for g in GrammarRule]))

        return self._transform_deck(deck, side, grammar_rules)
