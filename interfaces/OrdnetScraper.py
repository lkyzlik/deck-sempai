import httpx
from pathlib import Path
from bs4 import BeautifulSoup


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


    def _get_word_page(self, word: str) -> str | None:
        try:
            resp = self.client.get(self.BASE_URL, params={"query": word}, follow_redirects=True, timeout=15)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise OrdnetScraperError(f"Can't fetch word page")
        return resp.text
    

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
            raise OrdnetScraperError(f"Can't download sound file")
        
        if not output_path.parent.exists():
            output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "wb") as f:
            f.write(resp.content)


    def download_sound(self, word: str, filename: str) -> Path:
        html = self._get_word_page(word)
        sound_url = self._extract_sound_url(html)
        output_path = self.output_dir / filename
        self._download_file(sound_url, output_path)
        return output_path


class OrdnetScraperError(Exception):
    def __init__(self, message: str):
        super().__init__(f"'ordnet.dk' scraper: {message}")