import httpx
from bs4 import BeautifulSoup, Tag

from Enums import Language
from tools.GrammarTool import GrammarTool


class OrdnetIntegration:
    BASE_URL = "https://ordnet.dk/ddo/ordbog"
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    # A common word used to test connectivity: any dictionary entry being reachable confirms
    # both internet access and that ordnet.dk itself is up.
    TEST_WORD = "hus"

    # ordnet.dk's part-of-speech key for the homonym entry we should prefer, based on what
    # extract_word() found in the text (an infinitive marker implies a verb, an article a noun).
    POS_KEY_FOR_MARKER = "vb."
    POS_KEY_FOR_ARTICLE = "sb."


    def __init__(self):
        self.client = httpx.Client(headers=self.HEADERS)
        self._html_cache: dict[str, str] = {}
        self._grammar_tool = GrammarTool(Language.DANISH)
        self._enabled = True


    def enable(self, enable: bool):
        self._enabled = enable


    def configure(self, config: dict):
        pass


    def test_connection(self) -> bool:
        try:
            self.get_html(self.TEST_WORD)
            return True
        except OrdnetIntegrationError:
            return False


    def status(self) -> str:
        if not self._enabled:
            return "disabled"
        return "connected" if self.test_connection() else "not_connected"


    def user_help(self) -> str:
        return (
            "Can't reach ordnet.dk. Check your internet connection, then try again. "
            "If the problem persists, ordnet.dk may be down or blocking requests."
        )


    def get_html(self, text: str) -> str:
        if not self._enabled:
            raise OrdnetIntegrationDisabledError("Integration is disabled")

        extracted = self._grammar_tool.extract_word(text)
        word = extracted["word"]

        # A word's page can be looked up several times (e.g. for its part of speech, then its
        # inflections), so cache the raw page instead of refetching it each time.
        if word not in self._html_cache:
            try:
                resp = self.client.get(self.BASE_URL, params={"query": word}, follow_redirects=True, timeout=15)
                resp.raise_for_status()
            except httpx.HTTPError as e:
                raise OrdnetIntegrationError(f"Can't fetch word page")
            self._html_cache[word] = resp.text

        entry = self._select_entry(self._html_cache[word], word, extracted)
        return str(entry)


    def _select_entry(self, html: str, word: str, extracted: dict[str, str | None]) -> Tag:
        soup = BeautifulSoup(html, "html.parser")
        headwords = soup.find_all("h1", class_="modern-match")

        # A word already in its dictionary form matches a headword exactly (this also narrows
        # down to homonyms of that same spelling). A verb searched in a conjugated form won't
        # match any headword directly, but ordnet.dk still resolves the search to that verb's
        # own page, so fall back to whatever entries it found.
        entries = []
        for headword in headwords:
            # The headword text is followed by a superscript homonym number (e.g. "arbejde <sup>1</sup>"),
            # so only look at the leading text node when matching.
            base = (headword.find(string=True, recursive=False) or "").strip()
            if base.lower() == word.lower():
                entry = headword.find_parent("div", class_="artikel")
                if entry:
                    entries.append(entry)
        if not entries:
            entries = [e for e in (hw.find_parent("div", class_="artikel") for hw in headwords) if e]

        if not entries:
            raise OrdnetIntegrationError(f"Can't find a dictionary entry for {word!r}")

        # If the text told us it's a verb (infinitive marker) or a noun (article), prefer the
        # homonym entry with that part of speech; otherwise just take the site's default entry.
        wanted_pos = None
        if extracted["markers"]:
            wanted_pos = self.POS_KEY_FOR_MARKER
        elif extracted["articles"]:
            wanted_pos = self.POS_KEY_FOR_ARTICLE

        if wanted_pos:
            for entry in entries:
                pos_span = entry.find(class_="part-of-speech")
                if pos_span and pos_span.get("data-pos-key") == wanted_pos:
                    return entry

        return entries[0]


class OrdnetIntegrationError(Exception):
    def __init__(self, message: str):
        super().__init__(f"'ordnet.dk' integration: {message}")


class OrdnetIntegrationDisabledError(OrdnetIntegrationError):
    pass
