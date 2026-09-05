import httpx


class OrdnetIntegration:
    BASE_URL = "https://ordnet.dk/ddo/ordbog"
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }


    def __init__(self):
        self.client = httpx.Client(headers=self.HEADERS)
        self._html_cache: dict[str, str] = {}


    def get_html(self, word: str) -> str:
        # A word's page can be looked up several times (e.g. for its part of speech,
        # then its inflections), so cache it instead of refetching it each time.
        if word not in self._html_cache:
            try:
                resp = self.client.get(self.BASE_URL, params={"query": word}, follow_redirects=True, timeout=15)
                resp.raise_for_status()
            except httpx.HTTPError as e:
                raise OrdnetIntegrationError(f"Can't fetch word page")
            self._html_cache[word] = resp.text
        return self._html_cache[word]


class OrdnetIntegrationError(Exception):
    def __init__(self, message: str):
        super().__init__(f"'ordnet.dk' integration: {message}")
