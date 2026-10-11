from ollama import ChatResponse, Client, ResponseError


class OllamaIntegration:
    name = "ollama"

    def __init__(self):
        self._enabled = True
        self._host = None
        self._default_model = "gemma4"


    def enable(self, enable: bool):
        self._enabled = enable


    def configure(self, config: dict):
        if config.get("host"):
            self._host = config["host"]
        if config.get("default_model"):
            self._default_model = config["default_model"]


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
        return "running" if self.test_connection() else "disconnected"


    def user_help(self) -> str:
        return (
             "1. Make sure Ollama app is installed and running. (https://ollama.com/download)\n"
            f"2. Make sure that configured model '{self._default_model}' is installed. Run\n"
            f"   'ollama list' to see installed models and install new one with\n"
            f"   'ollama pull MODEL_NAME'."
        )


    def chat(self, messages: list[dict], model: str = None, think: bool | str = False,
             temperature: float = None, keep_alive: str = "10s") -> str:
        if not self._enabled:
            raise OllamaIntegrationDisabledError("Integration is disabled")

        options = {"temperature": temperature} if temperature is not None else None
        try:
            response: ChatResponse = self._client().chat(model or self._default_model, messages=messages, think=think,
                                                         keep_alive=keep_alive, options=options)
        except ConnectionError as e:
            raise OllamaIntegrationError(
                f"Can't reach Ollama. Run 'setup {self.name}' to check the connection and see repair steps."
            ) from e
        except ResponseError as e:
            raise OllamaIntegrationError("AI request failed") from e

        return response.message.content.strip()


class OllamaIntegrationError(Exception):
    def __init__(self, message: str):
        super().__init__(f"'Ollama' integration: {message}")


class OllamaIntegrationDisabledError(OllamaIntegrationError):
    pass
