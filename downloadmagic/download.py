import os
import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Dict
from urllib.parse import urlparse

import requests


class DownloadStatus(Enum):
    UNSTARTED = auto()
    IN_PROGRESS = auto()
    PAUSED = auto()
    COMPLETED = auto()
    CANCELED = auto()
    ERROR = auto()


class DownloadOperation(Enum):
    START = "START"
    PAUSE = "PAUSE"
    CANCEL = "PAUSE"


@dataclass
class Download:
    download_id: int
    url: str
    download_directory: str
    size: int
    filename: str
    filepath: str
    is_pausable: bool

    def to_dictionary(self) -> Dict[str, Any]:
        dictionary = {
            "download_id": self.download_id,
            "download_directory": self.download_directory,
            "size": self.size,
            "filename": self.filename,
            "filepath": self.filepath,
            "is_pausable": self.is_pausable,
        }
        return dictionary

    @staticmethod
    def _get_filename_from_url(url: str) -> str:
        parse_result = urlparse(url)
        filename = os.path.basename(parse_result.path)
        return filename

    @staticmethod
    def _get_filename(response: requests.Response, url: str) -> str:
        content_disposition = response.headers.get("Content-Disposition", "")
        if not content_disposition:
            return Download._get_filename_from_url(url)
        if match := re.search(r'filename="(.+?)"', content_disposition):
            filename: str = match.group(1)
            filename = os.path.basename(filename)
            return filename
        return Download._get_filename_from_url(url)

    @staticmethod
    def _get_pausable(response: requests.Response) -> bool:
        range_header = response.headers.get("Accept-Ranges", "")
        if not range_header:
            return False
        return range_header == "bytes"

    @classmethod
    def from_values(
        cls, download_id: int, url: str, download_directory: str
    ) -> "Download":
        response = requests.head(url, allow_redirects=True)
        size = int(response.headers["Content-Length"])
        filename = cls._get_filename(response, url)
        download_directory = os.path.abspath(download_directory)
        filepath = os.path.join(download_directory, filename)
        is_pausable = cls._get_pausable(response)
        download = Download(
            download_id, url, download_directory, size, filename, filepath, is_pausable
        )
        return download
