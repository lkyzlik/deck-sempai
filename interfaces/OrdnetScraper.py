import httpx
from pathlib import Path
from bs4 import BeautifulSoup, Tag


class OrdnetScraper:
    BASE_URL = "https://ordnet.dk/ddo/ordbog"
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }


    def __init__(self, output_dir: Path):
        self.client = httpx.Client(headers=self.HEADERS)
        self.output_dir = output_dir


    def _get_word_html(self, word: str) -> str | None:
        try:
            resp = self.client.get(self.BASE_URL, params={"query": word}, follow_redirects=True, timeout=15)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise OrdnetScraperError(f"Can't fetch word page")
        return resp.text


    def _find_entry(self, word: str) -> Tag:
        html = self._get_word_html(word)
        if not html:
            raise OrdnetScraperError(f"Can't fetch dictionary page for {word!r}")

        soup = BeautifulSoup(html, "html.parser")
        for headword in soup.find_all("h1", class_="modern-match"):
            # The headword text is followed by a superscript homonym number (e.g. "arbejde <sup>1</sup>"),
            # so only look at the leading text node when matching.
            base = (headword.find(string=True, recursive=False) or "").strip()
            if base.lower() == word.lower():
                entry = headword.find_parent("div", class_="artikel")
                if entry:
                    return entry

        raise OrdnetScraperError(f"Can't find a dictionary entry for {word!r}")


    def get_pos_key(self, word: str) -> str | None:
        pos_span = self._find_entry(word).find(class_="part-of-speech")
        return pos_span.get("data-pos-key") if pos_span else None


    def get_gender(self, word: str) -> str | None:
        pos_span = self._find_entry(word).find(class_="part-of-speech")
        if not pos_span:
            return None
        gender_text = pos_span.parent.get_text(" ", strip=True)
        if "fælleskøn" in gender_text:
            return "fælleskøn"
        if "intetkøn" in gender_text:
            return "intetkøn"
        return None


    def get_inflections(self, word: str) -> list[str]:
        row = self._find_entry(word).find("div", id="id-boj")
        button = row.find("button", class_="kilde") if row else None
        if not button:
            raise OrdnetScraperError(f"Can't find inflection info for {word!r}")
        return [form.strip() for form in button.get_text(strip=True).split(",")]


    def get_auxiliary_verbs(self, word: str) -> set[str]:
        # Verbs are annotated per valency pattern (one per sense) with which auxiliary
        # verb(s) ("have" and/or "være") form the perfect tense with that pattern. Verbs
        # that always take "have" aren't annotated at all.
        auxiliaries = set()
        for label in self._find_entry(word).find_all("span", class_="stempelSmallNoBorder", string="HJÆLPEVERBUM"):
            text = label.parent.get_text(" ", strip=True).split("HJÆLPEVERBUM")[-1]
            if "have" in text:
                auxiliaries.add("have")
            if "være" in text:
                auxiliaries.add("være")
        return auxiliaries


    def _extract_sound_url(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")

        lydskrift = soup.find("span", class_="lydskrift")
        if not lydskrift:
            raise OrdnetScraperError("Can't find sound URL")

        audio = lydskrift.find("audio")
        if not audio:
            raise OrdnetScraperError("Can't find sound URL")

        hidden_structure = audio.find("div", class_="hiddenStructure")
        if not hidden_structure:
            raise OrdnetScraperError("Can't find sound URL")

        a = hidden_structure.find("a")
        if a and a.get("href", "") and a["href"].endswith(".mp3"):
            return a["href"]
        else:
            raise OrdnetScraperError("Can't find sound URL")


    def _download_file(self, url: str, output_path: Path) -> None:
        try:
            resp = self.client.get(url, timeout=15)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise OrdnetScraperError(f"Can't download file")
        
        if not output_path.parent.exists():
            output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "wb") as f:
            f.write(resp.content)


    def download_sound(self, word: str, filename: str) -> Path:
        html = self._get_word_html(word)
        sound_url = self._extract_sound_url(html)
        output_path = self.output_dir / filename
        self._download_file(sound_url, output_path)
        return output_path


class OrdnetScraperError(Exception):
    def __init__(self, message: str):
        super().__init__(f"'ordnet.dk' scraper: {message}")