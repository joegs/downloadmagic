import threading as th
from typing import Dict, Optional, cast

from downloadmagic.download import Download, DownloadOperation
from downloadmagic.message import (
    DownloadInfoMessage,
    DownloadOperationMessage,
    DownloadStatusMessage,
    CreateDownloadMessage,
)
from downloadmagic.server.worker import DownloadWorker
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

    def _get_download_id(self) -> int:
        download_id = self._max_download_id
        self._max_download_id += 1
        return download_id

    def create_download(self, message: CreateDownloadMessage) -> None:
        download_id = self._get_download_id()
        worker = DownloadWorker(
            self.message_broker,
            download_id,
            message["url"],
            message["download_directory"],
        )
        worker.start()

    def _send_worker_message(
        self, download_id: int, download_operation: DownloadOperation
    ) -> None:
        topic = f"downloadworker{download_id}"
        message = DownloadOperationMessage(
            topic=topic,
            action="DownloadOperation",
            download_id=download_id,
            download_operation=download_operation.value,
        )
        self.message_broker.send_message(message)

    def start_download(self, download_id: int) -> None:
        self._send_worker_message(download_id, DownloadOperation.START)

    def pause_download(self, download_id: int) -> None:
        self._send_worker_message(download_id, DownloadOperation.PAUSE)

    def cancel_download(self, download_id: int) -> None:
        self._send_worker_message(download_id, DownloadOperation.CANCEL)

    def _receive_download_operation(self, message: DownloadOperationMessage) -> None:
        download_id: int = message["download_id"]
        operation: str = message["download_operation"]
        if operation == DownloadOperation.START.value:
            self.start_download(download_id)
        elif operation == DownloadOperation.PAUSE.value:
            self.pause_download(download_id)
        elif operation == DownloadOperation.CANCEL.value:
            self.cancel_download(download_id)

    def _receive_download_info(self, message: DownloadInfoMessage) -> None:
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
        download_info_message: DownloadInfoMessage = message.copy()
        download_info_message["topic"] = "downloadclient"
        self.message_broker.send_message(download_info_message)

    def _send_client_download_status(self, message: DownloadStatusMessage) -> None:
        download_id: int = message["download_id"]
        download: Optional[Download] = self.downloads.get(download_id, None)
        if download is None:
            return
        self.downloads_status[download_id] = message
        download_status_message = message.copy()
        download_status_message["topic"] = "downloadclient"
        self.message_broker.send_message(download_status_message)

    def _process_message(self, message: Message) -> None:
        action = message["action"]
        if action == "CreateDownload":
            create_download_message = cast(CreateDownloadMessage, message)
            self.create_download(create_download_message)
        elif action == "DownloadOperation":
            download_operation_message = cast(DownloadOperationMessage, message)
            self._receive_download_operation(download_operation_message)
        elif action == "DownloadInfo":
            download_info_message = cast(DownloadInfoMessage, message)
            self._receive_download_info(download_info_message)
        elif action == "DownloadStatus":
            download_status_message = cast(DownloadStatusMessage, message)
            self._send_client_download_status(download_status_message)

    def run(self) -> None:
        while True:
            self.subscriber.received.wait()
            for message in self.subscriber.messages():
                self._process_message(message)
