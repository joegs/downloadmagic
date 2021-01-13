import os
import threading as th
from typing import Any, Dict, cast, BinaryIO

import requests
from downloadmagic.download import Download, DownloadOperation, DownloadStatus
from downloadmagic.message import (
    DownloadInfoMessage,
    DownloadOperationMessage,
    DownloadStatusMessage,
)
from downloadmagic.utilities import Timer
from downloadmagic.youtube import download_youtube_mp3, get_youtube_video_info
from messaging import Message, MessageBroker, ThreadSubscriber


class DownloadWorker(th.Thread):
    """A download worker to manage a download.

    Each worker runs on its own thread, and communicates with the
    download server through a `MessageBroker`.

    Parameters
    ----------
    message_broker : MessageBroker
        The message broker instance to use for communication with the
        download server.
    download_id : int
        The id of the download that corresponds to this worker.
    url: str
        The url of the download that corresponds to this worker.
    download_directory : str
        The directory where the download content will be saved.

    Attributes
    ----------
    CHUNK_SIZE : int
        The amount of bytes to retrieve from the download connection on
        each download cycle.
    UPDATE_INTERVAL : float
        The minimum amount of seconds between updates. When an update
        happens, messages are received from the download server, and
        then processed.

    download: Download
        A download object with the download information.
    subscriber: ThreadSubscriber
        The subscriber instance used to receive the server messages.
    downloaded_bytes : int
        The amount of bytes that have already been downloaded.
    status : DownloadStatus
        The current status of the download
    speed : float
        The current speed of the download, in bytes per second.
    should_finish : bool
        A boolean that indicates whether or not the download should
        finish while it's in progress.
    message_broker : MessageBroker
        The message broker instance to use for communication with the
        download server.
    """

    CHUNK_SIZE = 1024 * 100  # 100 KB
    UPDATE_INTERVAL = 1

    def __init__(
        self,
        message_broker: MessageBroker,
        download_id: int,
        url: str,
        download_directory: str,
    ) -> None:
        super().__init__()
        self.download = self._get_placeholder_download(
            download_id, url, download_directory
        )
        self.subscriber = ThreadSubscriber({f"downloadworker{download_id}"})
        self.downloaded_bytes = 0
        self.status = DownloadStatus.UNSTARTED
        self.speed: float = 0
        self.should_finish: bool = False
        self.message_broker = message_broker
        self.message_broker.subscribe(self.subscriber)

    def run(self) -> None:
        self._initialize_download()
        if self.status == DownloadStatus.ERROR:
            self._terminate()
            return
        while True:
            self.subscriber.received.wait()
            for message in self.subscriber.messages():
                self._process_message(message)
            if self.status in (
                DownloadStatus.COMPLETED,
                DownloadStatus.CANCELED,
                DownloadStatus.ERROR,
            ):
                self._terminate()
                return

    def _initialize_download(self) -> None:
        try:
            self.download = Download.from_url(
                self.download.download_id,
                self.download.url,
                self.download.download_directory,
            )
        except requests.RequestException:
            self.download.filename = self.download.url
            self.status = DownloadStatus.ERROR
        message = DownloadInfoMessage(
            topic="downloadserver",
            action="DownloadInfo",
            download_id=self.download.download_id,
            url=self.download.url,
            download_directory=self.download.download_directory,
            size=self.download.size,
            filename=self.download.filename,
            filepath=self.download.filepath,
            is_pausable=self.download.is_pausable,
        )
        self.message_broker.send_message(message)
        self._send_download_status()

    def _terminate(self) -> None:
        self._send_download_status()
        if self.status in (DownloadStatus.CANCELED, DownloadStatus.ERROR):
            self._delete_file()
        self.message_broker.unsubscribe(self.subscriber)

    def _delete_file(self) -> None:
        filepath = self.download.filepath
        try:
            os.remove(filepath)
        except FileNotFoundError:
            pass

    def _get_placeholder_download(
        self, download_id: int, url: str, download_directory: str
    ) -> Download:
        download = Download(
            download_id=download_id,
            url=url,
            download_directory=download_directory,
            size=0,
            filename="",
            filepath="",
            is_pausable=False,
        )
        return download

    def _process_message(self, message: Message) -> None:
        if message["action"] != "DownloadOperation":
            return
        download_operation_message = cast(DownloadOperationMessage, message)
        operation: str = download_operation_message["download_operation"]
        if operation == DownloadOperation.START.value:
            self._start_operation()
        elif operation == DownloadOperation.CANCEL.value:
            self._cancel_operation()
        elif operation == DownloadOperation.PAUSE.value:
            self._pause_operation()

    def _start_operation(self) -> None:
        if self.status in (DownloadStatus.UNSTARTED, DownloadStatus.PAUSED):
            self.should_finish = False
            self._start_download()

    def _cancel_operation(self) -> None:
        if self.status != DownloadStatus.COMPLETED:
            self.status = DownloadStatus.CANCELED

    def _pause_operation(self) -> None:
        if self.status == DownloadStatus.IN_PROGRESS and self.download.is_pausable:
            self.status = DownloadStatus.PAUSED

    def _send_download_status(self) -> None:
        progress: float
        if self.download.size == 0:
            progress = 0
        else:
            progress = self.downloaded_bytes / self.download.size
        message = DownloadStatusMessage(
            topic="downloadserver",
            action="DownloadStatus",
            download_id=self.download.download_id,
            status=self.status.value,
            downloaded_bytes=self.downloaded_bytes,
            progress=progress,
            speed=self.speed,
        )
        self.message_broker.send_message(message)

    def _start_download(self) -> None:
        timer = Timer()
        timer.start()
        cycle_bytes = 0
        with self._get_response() as response, self._get_file_object() as file:
            self.status = DownloadStatus.IN_PROGRESS
            for chunk in response.iter_content(self.CHUNK_SIZE):
                file.write(chunk)
                self.downloaded_bytes += len(chunk)
                cycle_bytes += len(chunk)
                timer.measure()
                if (timer.elapsed_time) >= self.UPDATE_INTERVAL:
                    self._update()
                    if self.should_finish:
                        break
                    self.speed = cycle_bytes / timer.elapsed_time
                    cycle_bytes = 0
                    timer.start()
        self._finish_download()

    def _get_response(self) -> requests.Response:
        headers: Dict[str, str] = {}
        if self.status == DownloadStatus.PAUSED:
            headers = {"Range": f"bytes={self.downloaded_bytes}-{self.download.size}"}
        response = requests.get(self.download.url, stream=True, headers=headers)
        return response

    def _get_file_object(self) -> BinaryIO:
        mode = "wb"
        if self.status == DownloadStatus.PAUSED:
            mode = "ab"
        file_object: BinaryIO = cast(BinaryIO, open(self.download.filepath, mode))
        return file_object

    def _update(self) -> None:
        # Download is finished, don't process any more messages
        if self.downloaded_bytes == self.download.size:
            self._send_download_status()
            return
        for message in self.subscriber.messages():
            self._process_message(message)
        if self.status in (DownloadStatus.CANCELED, DownloadStatus.PAUSED):
            self.should_finish = True
        self._send_download_status()

    def _finish_download(self) -> None:
        if self.status in (DownloadStatus.CANCELED, DownloadStatus.PAUSED):
            return
        if self.downloaded_bytes == self.download.size:
            self.status = DownloadStatus.COMPLETED
        else:
            self.status = DownloadStatus.ERROR


class YoutubeDownloadWorker(DownloadWorker):
    def _initialize_download(self) -> None:
        video_info = get_youtube_video_info(self.download.url)
        filepath = os.path.join(
            self.download.download_directory,
            f"{video_info.title}.{video_info.extension}.part",
        )
        self.download = Download(
            download_id=self.download.download_id,
            url=self.download.url,
            download_directory=self.download.download_directory,
            size=video_info.filesize,
            filename=f"{video_info.title}.mp3",
            filepath=filepath,
            is_pausable=True,
        )
        message = DownloadInfoMessage(
            topic="downloadserver",
            action="DownloadInfo",
            download_id=self.download.download_id,
            url=self.download.url,
            download_directory=self.download.download_directory,
            size=self.download.size,
            filename=self.download.filename,
            filepath=self.download.filepath,
            is_pausable=self.download.is_pausable,
        )
        self.message_broker.send_message(message)
        self._send_download_status()

    def _progress_hook(self, download_progress: Dict[str, Any]) -> None:
        self.downloaded_bytes = download_progress.get("downloaded_bytes", 0)
        tmp_filename = download_progress.get("tmpfilename", None)
        if tmp_filename is not None:
            self.download.filepath = os.path.join(
                self.download.download_directory, tmp_filename
            )
        # The actual value on download_progress may also be None
        speed = download_progress.get("speed", None)
        if speed is None:
            speed = 0
        self.speed = speed
        self._update()
        if self.should_finish:
            raise ValueError()

    def _start_download(self) -> None:
        try:
            self.status = DownloadStatus.IN_PROGRESS
            download_youtube_mp3(
                self.download.url,
                self.download.download_directory,
                self._progress_hook,
            )
        except ValueError:
            pass
        self._finish_download()
