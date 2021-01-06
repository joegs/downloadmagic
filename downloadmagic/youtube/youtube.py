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
    title: str
    extension: str
    filesize: int


def download_youtube_mp3(
    youtube_url: str, download_directory: str, hook: DownloadHook
) -> None:
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
