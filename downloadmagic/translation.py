import gettext
import importlib.resources


class Translation:
    def __init__(self, language: str = "en"):
        self.language = language
        path = importlib.resources.files("downloadmagic") / "locale"  # type: ignore
        self._translations = {
            "en": gettext.translation("downloadmagic", path, languages=["en"]),
            "es": gettext.translation("downloadmagic", path, languages=["es"]),
            "ja": gettext.translation("downloadmagic", path, languages=["ja"]),
        }

    def translate(self, string: str) -> str:
        translation = self._translations[self.language]
        return translation.gettext(string)


def _translation_mark(string: str) -> str:
    return string


TR = Translation()

T_ = TR.translate
TM_ = _translation_mark
