import os
import threading as th
from typing import Dict, cast

from downloadmagic.download import Download, DownloadOperation
from downloadmagic.message import (
    CreateDownloadMessage,
    DownloadInfoMessage,
    DownloadOperationMessage,
    DownloadStatusMessage,
)
from downloadmagic.server.worker import DownloadWorker, YoutubeDownloadWorker
from messaging import Message, MessageBroker, ThreadSubscriber


class DownloadServer(th.Thread):
    def __init__(self, message_broker: MessageBroker) -> None:
        super().__init__(daemon=True)
        self.downloads: Dict[int, Download] = {}
        self.downloads_status: Dict[int, DownloadStatusMessage] = {}
        self.subscriber = ThreadSubscriber({"downloadserver"})
        self.message_broker = message_broker
        self.message_broker.subscribe(self.subscriber)
        self._max_download_id = 1

    def create_download(self, url: str, download_directory: str) -> None:
        """Create a download worker from the specified values.

        The download is not automatically started.

        Parameters
        ----------
        url : str
            The url of the download.
        download_directory : str
            The path where the download will be saved. This must be a
            directory, as the download filename will be automatically
            generated.
        """
        download_id = self._get_download_id()
        download_directory = os.path.abspath(download_directory)
        worker: DownloadWorker
        if "youtube.com" in url or "youtu.be" in url:
            worker = YoutubeDownloadWorker(
                self.message_broker, download_id, url, download_directory
            )
        else:
            worker = DownloadWorker(
                self.message_broker, download_id, url, download_directory
            )
        worker.start()

    def start_download(self, download_id: int) -> None:
        """Start the download with the specified id."""
        self._send_worker_message(download_id, DownloadOperation.START)

    def pause_download(self, download_id: int) -> None:
        """Pause the download with the specified id."""
        self._send_worker_message(download_id, DownloadOperation.PAUSE)

    def cancel_download(self, download_id: int) -> None:
        """Cancel the download with the specified id."""
        self._send_worker_message(download_id, DownloadOperation.CANCEL)

    def _get_download_id(self) -> int:
        """Generate a unique download id.

        Returns
        -------
        int
            A unique download id.
        """
        download_id = self._max_download_id
        self._max_download_id += 1
        return download_id

    def _send_worker_message(
        self, download_id: int, download_operation: DownloadOperation
    ) -> None:
        """Send a download operation message to a download worker.

        The worker that will receive the message is the one that has
        the same `download_id`.

        Parameters
        ----------
        download_id : int
            The download id that corresponds to the download of the
            download worker.
        download_operation : DownloadOperation
            The download operation for the message.
        """
        topic = f"downloadworker{download_id}"
        message = DownloadOperationMessage(
            topic=topic,
            action="DownloadOperation",
            download_id=download_id,
            download_operation=download_operation.value,
        )
        self.message_broker.send_message(message)

    def _receive_create_download_message(self, message: CreateDownloadMessage) -> None:
        """Receive a create download message.

        A new download worker will be created from the information in
        the message.

        Parameters
        ----------
        message : CreateDownloadMessage
        """
        self.create_download(message["url"], message["download_directory"])

    def _receive_download_operation_message(
        self, message: DownloadOperationMessage
    ) -> None:
        """Receive a download operation message.

        Based on the info of the message, a download operation message
        will be sent to the appropiate download worker.

        Parameters
        ----------
        message : DownloadOperationMessage
        """
        download_id: int = message["download_id"]
        operation: str = message["download_operation"]
        if operation == DownloadOperation.START.value:
            self.start_download(download_id)
        elif operation == DownloadOperation.PAUSE.value:
            self.pause_download(download_id)
        elif operation == DownloadOperation.CANCEL.value:
            self.cancel_download(download_id)

    def _receive_download_info_message(self, message: DownloadInfoMessage) -> None:
        """Receive a download info message.

        A download is created from the information in the message, and
        stored in `downloads`. The message is then forwarded to the
        client, only changing the topic of the message.

        Parameters
        ----------
        message : DownloadInfoMessage
        """
        download = Download(
            download_id=message["download_id"],
            url=message["url"],
            download_directory=message["download_directory"],
            size=message["size"],
            filename=message["filename"],
            filepath=message["filepath"],
            is_pausable=message["is_pausable"],
        )
        self.downloads[message["download_id"]] = download
        message["topic"] = "downloadclient"
        self.message_broker.send_message(message)

    def _receive_download_status(self, message: DownloadStatusMessage) -> None:
        """Receive a download status message.

        The message is stored for reference in `downloads_status`, and
        it is then forwarded to the client, only changing the topic of
        the message.

        Parameters
        ----------
        message : DownloadStatusMessage
        """
        download_id: int = message["download_id"]
        download = self.downloads.get(download_id, None)
        if download is None:
            return
        self.downloads_status[download_id] = message
        message["topic"] = "downloadclient"
        self.message_broker.send_message(message)

    def _process_message(self, message: Message) -> None:
        action = message["action"]
        if action == "CreateDownload":
            create_download_message = cast(CreateDownloadMessage, message)
            self._receive_create_download_message(create_download_message)
        elif action == "DownloadOperation":
            download_operation_message = cast(DownloadOperationMessage, message)
            self._receive_download_operation_message(download_operation_message)
        elif action == "DownloadInfo":
            download_info_message = cast(DownloadInfoMessage, message)
            self._receive_download_info_message(download_info_message)
        elif action == "DownloadStatus":
            download_status_message = cast(DownloadStatusMessage, message)
            self._receive_download_status(download_status_message)

    def run(self) -> None:
        while True:
            self.subscriber.received.wait()
            for message in self.subscriber.messages():
                self._process_message(message)
