import requests

class AnkiConnect:
    def __init__(self, host="localhost", port=8765):
        self.host = host
        self.port = port

    
    def _invoke(self, action, **params):
        try:
            response = requests.post(f'http://{self.host}:{self.port}', json={
                "action": action,
                "version": 6,
                "params": params
            })
        except requests.RequestException:
            raise AnkiConnectError("Can't connect. Anki app must be running to use this feature.")
        result = response.json()
        if result.get("error"):
            raise AnkiConnectError(result["error"])
        return result["result"]
    

    def version(self):
        return self._invoke("version")
    

    def deck_names(self):
        return self._invoke("deckNames")


    def find_notes(self, query):
        return self._invoke("findNotes", query=query)
    

    def notes_info(self, note_ids):
        return self._invoke("notesInfo", notes=note_ids)
    

    def add_note(self, note):
        return self._invoke("addNote", note=note)
    

    def add_notes(self, notes):
        return self._invoke("addNotes", notes=notes)
    

    def update_note(self, note):
        return self._invoke("updateNoteFields", note=note)
    

class AnkiConnectError(Exception):
    def __init__(self, message: str):
        super().__init__(f'AnkiConnect: {message}')
    
