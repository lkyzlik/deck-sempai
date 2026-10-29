from deck_sempai.Enums import Language


class TranslateToolError(Exception):
    pass


class TranslateToolDisabledError(TranslateToolError):
    pass


class TranslateTool:
    def __init__(self, lang_from: Language, lang_to: Language) -> None:
        self.lang_from = lang_from
        self.lang_to = lang_to

    def translate(self, text: str) -> str:
        raise NotImplementedError
