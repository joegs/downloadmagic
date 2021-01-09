import os
from dataclasses import dataclass
from typing import Any, Callable, Dict

from youtube_dl import YoutubeDL

DownloadHook = Callable[[Dict[str, Any]], None]

_YDL_OPTS = {
    "format": "bestaudio/best",
    "outtmpl": "%(title)s.%(ext)s",
    "postprocessors": [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }
    ],
    "quiet": True,
}


@dataclass
class VideoInfo:
    """An object that contains data from a youtube video."""

    title: str
    extension: str
    filesize: int


def download_youtube_mp3(
    youtube_url: str,
    download_directory: str,
    hook: DownloadHook,
) -> None:
    """Download a youtube video as an mp3 file.

    The mp3 file is saved into `download_directory`. The filename of
    the mp3 is the same as the video title.

    Parameters
    ----------
    youtube_url : str
        The url of the youtube video.
    download_directory : str
        The directory where the mp3 file will be downloaded to.
    hook : DownloadHook
        A function that accepts a dictionary as an argument and returns
        `None`. This function is executed periodically, and the
        dictionary passed to it contains the status of the download.
        For more information see youtube_dl documentation.
    """
    options: Dict[str, Any] = {
        "progress_hooks": [hook],
    }
    options |= _YDL_OPTS  # type: ignore
    options["outtmpl"] = os.path.join(download_directory, options["outtmpl"])
    with YoutubeDL(options) as ydl:
        ydl.download([youtube_url])


def get_youtube_video_info(youtube_url: str) -> VideoInfo:
    with YoutubeDL(_YDL_OPTS) as ydl:
        info_dict = ydl.extract_info(
            youtube_url,
            download=False,
        )
        video_info = VideoInfo(
            title=info_dict["title"],
            extension=info_dict["ext"],
            filesize=info_dict["filesize"],
        )
        return video_info
