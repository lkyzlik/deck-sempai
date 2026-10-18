import base64
import json
import requests

from pathlib import Path

class AnkiIntegration:
    name = "anki"

    LEGACY_METADATA_KEY = "sempai"
    MULTI_BATCH_SIZE = 100  # AnkiConnect's batch item limit

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


    def multi(self, actions: list[dict]) -> list:
        """Runs actions in batched requests. A failed action's result is an AnkiIntegrationError,
        so is every action's result in a batch whose whole request failed."""
        results = []
        for start in range(0, len(actions), self.MULTI_BATCH_SIZE):
            batch = actions[start:start + self.MULTI_BATCH_SIZE]
            try:
                batch_results = self._invoke("multi", actions=batch)
            except AnkiIntegrationDisabledError:
                raise
            except AnkiIntegrationError as e:
                results += [e] * len(batch)
                continue
            results += [AnkiIntegrationError(r["error"]) if isinstance(r, dict) and r.get("error") else r
                        for r in batch_results]
        return results


    def add_notes(self, notes: list[dict]) -> list:
        # Not "addNotes", which fails the whole batch if any note is invalid
        return self.multi([{"action": "addNote", "params": {"note": note}} for note in notes])


    def update_notes(self, notes: list[dict]) -> list:
        return self.multi([{"action": "updateNote", "params": {"note": note}} for note in notes])


    def _is_local(self) -> bool:
        return self.host in ("localhost", "127.0.0.1", "::1")


    def _store_media_params(self, filename: str, path: Path) -> dict:
        # Local Anki reads the file itself, which is much faster than sending base64
        if self._is_local():
            return {"filename": filename, "path": str(path.resolve())}

        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")
        return {"filename": filename, "data": data}


    def store_media_files(self, files: list[tuple[str, Path]]) -> list:
        params = []
        for filename, path in files:
            try:
                params.append(self._store_media_params(filename, path))
            except OSError as e:
                params.append(AnkiIntegrationError(f"Can't read file {path}: {e}"))

        outcomes = iter(self.multi([{"action": "storeMediaFile", "params": p}
                                    for p in params if not isinstance(p, AnkiIntegrationError)]))
        return [p if isinstance(p, AnkiIntegrationError) else next(outcomes) for p in params]


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


    def delete_media_files(self, filenames: list[str]) -> list:
        return self.multi([{"action": "deleteMediaFile", "params": {"filename": f}} for f in filenames])


    def get_deck_config(self, deck_name: str) -> dict:
        config = self._invoke("getDeckConfig", deck=deck_name)
        # AnkiConnect returns False instead of an error for a missing deck
        if not config:
            raise AnkiIntegrationError(f"Deck {deck_name!r} not found")
        return config


    def _private_config_prefix(self, deck_name: str) -> str:
        return f"sempai::{deck_name}"


    def _is_private_config(self, config: dict, deck_name: str) -> bool:
        # Decks share config groups (e.g. "Default") unless split off. Only trust metadata
        # in a group we've privately cloned for this deck, named "<prefix> <meta as JSON>".
        prefix = self._private_config_prefix(deck_name)
        return config.get("name") == prefix or config.get("name", "").startswith(prefix + " ")


    def get_deck_meta(self, deck_name: str) -> dict:
        config = self.get_deck_config(deck_name)
        if not self._is_private_config(config, deck_name):
            return {}
        meta_json = config["name"][len(self._private_config_prefix(deck_name)):].strip()
        if not meta_json:
            return config.get(self.LEGACY_METADATA_KEY, {})  # Saved by older AnkiConnect
        try:
            meta = json.loads(meta_json)
        except json.JSONDecodeError:
            return {}
        return meta if isinstance(meta, dict) else {}


    def save_deck_meta(self, deck_name: str, meta: dict) -> None:
        # New AnkiConnect rejects custom config keys and can't rename groups, so the metadata
        # lives in the name of a fresh clone of the deck's group, replacing our old private one
        name = f"{self._private_config_prefix(deck_name)} {json.dumps(meta)}"
        config = self.get_deck_config(deck_name)
        if config["name"] == name:
            return
        new_id = self._invoke("cloneDeckConfigId", cloneFrom=config["id"], name=name)
        self._invoke("setDeckConfigId", decks=[deck_name], configId=new_id)
        if self._is_private_config(config, deck_name):
            self._invoke("removeDeckConfigId", configId=config["id"])


class AnkiIntegrationError(Exception):
    def __init__(self, message: str):
        super().__init__(f"'Anki' integration: {message}")


class AnkiIntegrationDisabledError(AnkiIntegrationError):
    pass
