import os
import threading as th
from typing import Any, Dict, cast

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
        super().__init__(daemon=True)
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
        while True:
            self.subscriber.received.wait()
            self._process_messsages()
            if self.status in (DownloadStatus.COMPLETED, DownloadStatus.CANCELED):
                return

    def _get_placeholder_download(
        self, download_id: int, url: str, download_directory: str
    ) -> Download:
        """Return a placeholder download object.

        Only some of the values of this object are set to real values.
        The rest are placeholder values. They are set when the download
        is initialized.

        Parameters
        ----------
        download_id : int
        url : str
        download_directory : str

        Returns
        -------
        Download
        """
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

    def _initialize_download(self) -> None:
        # TODO add a timeout to this, and set the download status
        # as error if it times out
        self.download = Download.from_url(
            self.download.download_id,
            self.download.url,
            self.download.download_directory,
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

    def _process_messsages(self) -> None:
        for message in self.subscriber.messages():
            self._process_message(message)

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
        """Start or resume the download.

        The download can only be started or resumed if it hasn't
        started or it's paused.
        """
        if self.status in (DownloadStatus.UNSTARTED, DownloadStatus.PAUSED):
            self.should_finish = False
            self._start_download()

    def _cancel_operation(self) -> None:
        """Cancel the download.

        The download can only be canceled if it isn't completed.
        """
        if self.status != DownloadStatus.COMPLETED:
            if self.status == DownloadStatus.PAUSED:
                self._delete_file()
            self.status = DownloadStatus.CANCELED
            self._send_download_status()

    def _pause_operation(self) -> None:
        """Pause the download.

        The download can only be paused if it's currently in progress
        and the download connection supports pausing.
        """
        if self.status == DownloadStatus.IN_PROGRESS and self.download.is_pausable:
            self.status = DownloadStatus.PAUSED
            self._send_download_status()

    def _send_download_status(self) -> None:
        """Send a download status message to the server."""
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

    def _delete_file(self) -> None:
        """Delete the file that corresponds to the download."""
        filepath = self.download.filepath
        try:
            os.remove(filepath)
        except FileNotFoundError:
            pass

    def _finish_download(self) -> None:
        """Finish the download.

        Finishing the download means setting the correct status, and
        performing the appropiate actions for that status.
        """
        if self.status == DownloadStatus.CANCELED:
            self._delete_file()
            return
        if self.status == DownloadStatus.PAUSED:
            return
        if self.downloaded_bytes != self.download.size:
            self.status = DownloadStatus.ERROR
        else:
            self.status = DownloadStatus.COMPLETED
        self._send_download_status()

    def _update(self, cycle_bytes: int, timer: Timer) -> None:
        """Update the download while it's in progress.

        Parameters
        ----------
        cycle_bytes : int
            The amount of bytes downloaded in the current cycle.
        timer : Timer
            The timer object used to measure the download update
            interval.
        """
        # Download is finished, don't process any more messages
        if self.downloaded_bytes == self.download.size:
            self.should_finish = True
            return
        self.speed = cycle_bytes / timer.elapsed_time
        self._process_messsages()
        if self.status in (
            DownloadStatus.CANCELED,
            DownloadStatus.PAUSED,
        ):
            self.should_finish = True
            return
        self._send_download_status()
        timer.start()

    def _start_download(self) -> None:
        """Start or resume the download."""
        mode = "wb"
        headers = {}
        if self.status == DownloadStatus.PAUSED:
            headers = {"Range": f"bytes={self.downloaded_bytes}-{self.download.size}"}
            mode = "ab"
        timer = Timer()
        timer.start()
        cycle_bytes = 0
        # Use of context managers, the response and the file are both closed once
        # the block terminates, even in an unhandled exception occurs.
        with requests.get(self.download.url, stream=True, headers=headers) as response:
            with open(self.download.filepath, mode) as file:
                self.status = DownloadStatus.IN_PROGRESS
                for chunk in response.iter_content(self.CHUNK_SIZE):
                    file.write(chunk)
                    self.downloaded_bytes += len(chunk)
                    cycle_bytes += len(chunk)
                    timer.measure()
                    if (timer.elapsed_time) >= self.UPDATE_INTERVAL:
                        self._update(cycle_bytes, timer)
                        if self.should_finish:
                            break
                        cycle_bytes = 0
            self._finish_download()


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
        self._update_download()
        if self.should_finish:
            raise ValueError()

    def _update_download(self) -> None:
        if self.downloaded_bytes == self.download.size:
            self._send_download_status()
            return
        self._process_messsages()
        if self.status in (
            DownloadStatus.CANCELED,
            DownloadStatus.PAUSED,
        ):
            self.should_finish = True
            return
        self._send_download_status()

    def _start_download(self) -> None:
        try:
            self.status = DownloadStatus.IN_PROGRESS
            download_youtube_mp3(self.download.url, self._progress_hook)
        except ValueError:
            pass
        self._finish_download()
