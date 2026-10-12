import httpx
from bs4 import BeautifulSoup, Tag


class OrdnetIntegration:
    name = "ordnet"

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

    def __init__(self):
        self.client = httpx.Client(headers=self.HEADERS)
        self._entry_cache: dict[tuple[str, str | None], dict] = {}
        self._enabled = True


    def enable(self, enable: bool):
        self._enabled = enable


    def configure(self, config: dict):
        pass


    def test_connection(self) -> bool:
        try:
            self.get_entry(self.TEST_WORD)
            return True
        except OrdnetIntegrationError:
            return False


    def status(self) -> str:
        if not self._enabled:
            return "disabled"
        return "running" if self.test_connection() else "disconnected"


    def user_help(self) -> str:
        return (
            "1. Make sure your computer is connected to the internet.\n"
            "2. Check if ordnet.dk website is up."
        )



    def get_entry(self, word: str, pos: str = None) -> dict:
        if not self._enabled:
            raise OrdnetIntegrationDisabledError("Integration is disabled")

        # A word can be looked up several times (e.g. for its part of speech, then its
        # inflections), so cache the parsed entry instead of refetching and reparsing it each time.
        cache_key = (word, pos)
        if cache_key not in self._entry_cache:
            try:
                resp = self.client.get(self.BASE_URL, params={"query": word}, follow_redirects=True, timeout=15)
                resp.raise_for_status()
            except httpx.HTTPError:
                raise OrdnetIntegrationError(
                    f"Can't reach ordnet.dk to fetch word page. Run 'status {self.name}' to check the "
                    "connection and see repair steps."
                )
            article = self._select_entry(resp.text, word, pos)
            self._entry_cache[cache_key] = self._parse_entry(article)

        return self._entry_cache[cache_key]


    def _select_entry(self, html: str, word: str, pos: str | None) -> Tag:
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

        if pos:
            for entry in entries:
                pos_span = entry.find(class_="part-of-speech")
                if pos_span and pos_span.get("data-pos-key") == pos:
                    return entry

        return entries[0]


    def _parse_entry(self, entry: Tag) -> dict:
        return {
            "headword": self._headword(entry),
            "pos": self._pos(entry),
            "gender": self._gender(entry),
            "inflections": self._inflections(entry),
            "auxiliary_verb": self._auxiliary_verb(entry),
            "sound_url": self._sound_url(entry),
        }


    def _headword(self, entry: Tag) -> str | None:
        headword = entry.find("h1", class_="modern-match")
        if not headword:
            return None
        return (headword.find(string=True, recursive=False) or "").strip() or None


    def _pos(self, entry: Tag) -> str | None:
        pos_span = entry.find(class_="part-of-speech")
        return pos_span.get("data-pos-key") if pos_span else None


    def _gender(self, entry: Tag) -> str | None:
        pos_span = entry.find(class_="part-of-speech")
        if not pos_span:
            return None
        gender_text = pos_span.parent.get_text(" ", strip=True)
        if "fælleskøn" in gender_text:
            return "fælleskøn"
        if "intetkøn" in gender_text:
            return "intetkøn"
        return None


    def _inflections(self, entry: Tag) -> list[str]:
        row = entry.find("div", id="id-boj")
        button = row.find("button", class_="kilde") if row else None
        if not button:
            return []
        return [form.strip() for form in button.get_text(strip=True).split(",")]


    def _auxiliary_verb(self, entry: Tag) -> str:
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


    def _sound_url(self, entry: Tag) -> str | None:
        lydskrift = entry.find("span", class_="lydskrift")
        audio = lydskrift.find("audio") if lydskrift else None
        hidden_structure = audio.find("div", class_="hiddenStructure") if audio else None
        a = hidden_structure.find("a") if hidden_structure else None
        if a and a.get("href", "").endswith(".mp3"):
            return a["href"]
        return None


class OrdnetIntegrationError(Exception):
    def __init__(self, message: str):
        super().__init__(f"'ordnet.dk' integration: {message}")


class OrdnetIntegrationDisabledError(OrdnetIntegrationError):
    pass
