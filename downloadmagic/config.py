import importlib.resources
from enum import Enum, auto
from typing import Dict

import toml

from downloadmagic.translation import TR


class ConfigOption(Enum):
    DOWNLOAD_DIRECTORY = auto()
    LANGUAGE = auto()


class Configuration:

    DEFAULTS = {
        ConfigOption.DOWNLOAD_DIRECTORY: ".",
        ConfigOption.LANGUAGE: "en",
    }

    OPTIONS = {
        "DownloadDirectory": ConfigOption.DOWNLOAD_DIRECTORY,
        "Language": ConfigOption.LANGUAGE,
    }

    def __init__(self) -> None:
        self.configuration: Dict[ConfigOption, str] = {}

    def get_config_value(self, option: ConfigOption) -> str:
        value = self.configuration.get(option, None)
        if value is None:
            value = self.DEFAULTS[option]
        return value

    def set_config_value(self, option: ConfigOption, value: str) -> None:
        self.configuration[option] = value
        if option == ConfigOption.LANGUAGE:
            TR.language = value

    def load_config(self) -> None:
        path = importlib.resources.files("downloadmagic")  # type: ignore
        config_file = path / "config.toml"
        with open(config_file, "r") as file:
            configuration = toml.load(file)
            for k, v in configuration.items():
                if k in self.OPTIONS:
                    option = self.OPTIONS[k]
                    self.configuration[option] = v
