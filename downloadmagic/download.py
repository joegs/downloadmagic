import os
import re
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse

import requests


class DownloadStatus(Enum):
    UNSTARTED = "UNSTARTED"
    IN_PROGRESS = "IN_PROGRESS"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    CANCELED = "CANCELED"
    ERROR = "ERROR"


class DownloadOperation(Enum):
    START = "START"
    PAUSE = "PAUSE"
    CANCEL = "CANCEL"


@dataclass
class Download:
    """Container for the information of a download.

    Attributes
    ----------
    download_id : int
        The unique id of the download.
    url: str
        The url of the download.
    download_directory
        The directory where the download will be saved to.
    size : int
        The size of the download, in bytes.
    filename : str
        The filename of the download.
    is_pausable : bool
        Indicates whether or not the download can be paused and resumed
        later.

    filepath : str
        The file path where the download will be saved to. This is a
        computed property. It's the concatenation of
        `download_directory` and `filename`.
    """

    download_id: int
    url: str
    size: int = 0
    download_directory: str = ""
    filename: str = ""
    is_pausable: bool = False

    @property
    def filepath(self) -> str:
        return os.path.join(self.download_directory, self.filename)

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
    def from_url(
        cls,
        download_id: int,
        url: str,
        download_directory: str,
        timeout: int = 10,
    ) -> "Download":
        """Create a `Download` instance from a url.

        The values are computed by making an http request to the url,
        so this method may fail and raise an exception.

        Returns
        -------
        Download
            The resulting download.
        """
        response = requests.head(url, allow_redirects=True, timeout=timeout)
        size = int(response.headers["Content-Length"])
        filename = cls._get_filename(response, url)
        download_directory = os.path.abspath(download_directory)
        is_pausable = cls._get_pausable(response)
        download = Download(
            download_id,
            url,
            size,
            download_directory,
            filename,
            is_pausable,
        )
        return download
