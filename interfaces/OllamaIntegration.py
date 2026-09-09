from ollama import ChatResponse, Client, ResponseError


class OllamaIntegration:
    def __init__(self):
        self._enabled = True
        self._host = None


    def enable(self, enable: bool):
        self._enabled = enable


    def configure(self, config: dict):
        if "host" in config:
            self._host = config["host"]


    def _client(self) -> Client:
        return Client(host=self._host) if self._host else Client()


    def test_connection(self) -> bool:
        if not self._enabled:
            return False
        try:
            self._client().list()
            return True
        except (ResponseError, ConnectionError):
            return False


    def status(self) -> str:
        if not self._enabled:
            return "disabled"
        return "connected" if self.test_connection() else "not_connected"


    def user_help(self) -> str:
        return (
            "Can't reach Ollama. Make sure the Ollama server is running "
            "(see https://ollama.com), then try again."
        )


    def chat(self, model: str, messages: list[dict], think: bool | str = False,
             temperature: float = None, keep_alive: str = "10s") -> str:
        if not self._enabled:
            raise OllamaIntegrationDisabledError("Integration is disabled")

        options = {"temperature": temperature} if temperature is not None else None
        try:
            response: ChatResponse = self._client().chat(model, messages=messages, think=think,
                                                          keep_alive=keep_alive, options=options)
        except (ResponseError, ConnectionError) as e:
            raise OllamaIntegrationError("AI request failed") from e

        return response.message.content.strip()


class OllamaIntegrationError(Exception):
    def __init__(self, message: str):
        super().__init__(f"'Ollama' integration: {message}")


class OllamaIntegrationDisabledError(OllamaIntegrationError):
    pass
