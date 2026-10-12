import base64
import requests

from pathlib import Path

class AnkiIntegration:
    name = "anki"

    METADATA_KEY = "sempai"

    def __init__(self, host="localhost", port=8765):
        self.host = host
        self.port = port
        self._enabled = True


    def enable(self, enable: bool):
        self._enabled = enable


    def configure(self, config: dict):
        if config.get("host"):
            self.host = config["host"]
        if config.get("port"):
            self.port = config["port"]


    def test_connection(self) -> bool:
        if not self._enabled:
            return False
        try:
            self._invoke("version")
            return True
        except AnkiIntegrationError:
            return False


    def status(self) -> str:
        if not self._enabled:
            return "disabled"
        return "running" if self.test_connection() else "disconnected"


    def user_help(self) -> str:
        return (
            "1. Make sure Anki app is installed and running. (https://apps.ankiweb.net)\n"
            "2. Make sure AnkiConnect add-on is installed. Steps to install:\n"
            "   Tools > Add-ons > Get add-ons... > Code: 2055492159"
        )


    def _invoke(self, action, **params) -> dict:
        if not self._enabled:
            raise AnkiIntegrationDisabledError("Integration is disabled")

        try:
            response = requests.post(f'http://{self.host}:{self.port}', json={
                "action": action,
                "version": 6,
                "params": params
            })
        except requests.RequestException:
            raise AnkiIntegrationError(f"Can't connect. Run 'status {self.name}' to check the connection and see repair steps.")
        result = response.json()
        if result.get("error"):
            raise AnkiIntegrationError(result["error"])
        return result["result"]


    def version(self) -> int:
        return self._invoke("version")


    def deck_names(self) -> list[str]:
        return self._invoke("deckNames")


    def create_deck(self, deck_name: str) -> None:
        self._invoke("createDeck", deck=deck_name)


    def delete_deck(self, deck_name: str) -> None:
        self._invoke("deleteDecks", decks=[deck_name], cardsToo=True)


    def find_notes(self, query: str) -> list[int]:
        return self._invoke("findNotes", query=query)


    def notes_info(self, note_ids: list[int]) -> list[dict]:
        return self._invoke("notesInfo", notes=note_ids)


    def add_note(self, note: dict) -> int:
        return self._invoke("addNote", note=note)


    def add_notes(self, notes: list[dict]) -> list[bool]:
        return self._invoke("addNotes", notes=notes)


    def update_note(self, note: dict) -> None:
        return self._invoke("updateNoteFields", note=note)


    def store_media_file(self, filename: str, path: Path) -> None:
        if not self._enabled:
            raise AnkiIntegrationDisabledError("Integration is disabled")

        try:
            with open(path, "rb") as f:
                data = base64.b64encode(f.read()).decode("utf-8")
        except (base64.binascii.Error, UnicodeDecodeError) as e:
            raise AnkiIntegrationError(f"Can't encode file {path}: {e}")

        return self._invoke("storeMediaFile", filename=filename, data=data)


    def retrieve_media_file(self, filename: str, path: Path) -> None:
        data = self._invoke("retrieveMediaFile", filename=filename)
        try:
            binary_data = base64.b64decode(data)
        except (base64.binascii.Error, IOError) as e:
            raise AnkiIntegrationError(f"Can't decode file {filename!r}: {e}")

        if not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "wb") as f:
            f.write(binary_data)


    def delete_media_file(self, filename: str) -> None:
        return self._invoke("deleteMediaFile", filename=filename)


    def get_deck_config(self, deck_name: str) -> dict:
        return self._invoke("getDeckConfig", deck=deck_name)


    def save_deck_config(self, deck_name: str, config: dict) -> None:
        return self._invoke("saveDeckConfig", config=config)


    def _private_config_name(self, deck_name: str) -> str:
        return f"sempai::{deck_name}"


    def get_deck_meta(self, deck_name: str) -> dict:
        config = self.get_deck_config(deck_name)
        # Decks share config groups (e.g. "Default") unless split off. Only trust
        # metadata found in a group we've privately cloned for this deck, otherwise
        # it belongs to whichever other deck last wrote to the shared group.
        if config.get("name") != self._private_config_name(deck_name):
            return {}
        return config.get(self.METADATA_KEY, {})


    def save_deck_meta(self, deck_name: str, meta: dict) -> None:
        config = self.get_deck_config(deck_name)
        private_name = self._private_config_name(deck_name)
        if config.get("name") != private_name:
            new_id = self._invoke("cloneDeckConfigId", cloneFrom=config["id"], name=private_name)
            self._invoke("setDeckConfigId", decks=[deck_name], configId=new_id)
            config = self.get_deck_config(deck_name)
        config[self.METADATA_KEY] = meta
        self.save_deck_config(deck_name, config)


class AnkiIntegrationError(Exception):
    def __init__(self, message: str):
        super().__init__(f"'Anki' integration: {message}")


class AnkiIntegrationDisabledError(AnkiIntegrationError):
    pass
