import threading as th
from typing import Any, Dict, Optional

from downloadmagic.download import Download, DownloadOperation, DownloadStatus
from downloadmagic.server.worker import DownloadWorker
from downloadmagic.utilities import convert_size, convert_time
from messaging import Message, MessageBroker, ThreadSubscriber


class DownloadServer(th.Thread):
    def __init__(self, message_broker: MessageBroker) -> None:
        super().__init__(daemon=True)
        self.downloads: Dict[int, Download] = {}
        self.downloads_status: Dict[int, Dict[str, Any]] = {}
        self.subscriber = ThreadSubscriber({"downloadserver"})
        self.message_broker = message_broker
        self.message_broker.subscribe(self.subscriber)
        self._max_download_id = 1

    def _get_download_id(self) -> int:
        download_id = self._max_download_id
        self._max_download_id += 1
        return download_id

    def create_download(self, url: str, download_directory: str = ".") -> None:
        download_id = self._get_download_id()
        worker = DownloadWorker(
            self.message_broker, download_id, url, download_directory
        )
        worker.start()

    def _send_worker_message(
        self, download_id: int, download_operation: DownloadOperation
    ) -> None:
        message = {
            "topic": f"downloadworker{download_id}",
            "download_operation": download_operation.value,
        }
        self.message_broker.send_message(message)

    def start_download(self, download_id: int) -> None:
        self._send_worker_message(download_id, DownloadOperation.START)

    def pause_download(self, download_id: int) -> None:
        self._send_worker_message(download_id, DownloadOperation.PAUSE)

    def cancel_download(self, download_id: int) -> None:
        self._send_worker_message(download_id, DownloadOperation.CANCEL)

    def _receive_download_info(
        self, download_id: int, download_info: Dict[str, Any]
    ) -> None:
        download = Download(
            download_id=download_info["download_id"],
            url=download_info["url"],
            download_directory=download_info["download_directory"],
            size=download_info["size"],
            filename=download_info["filename"],
            filepath=download_info["filepath"],
            is_pausable=download_info["is_pausable"],
        )
        self.downloads[download_id] = download

    def _send_client_download_status(self, message: Message) -> None:
        download_id: int = message["download_id"]
        download: Optional[Download] = self.downloads.get(download_id, None)
        if download is None:
            return
        cached_status = self.downloads_status.get(download_id, None)
        action = "ClientUpdateDownload"
        if cached_status is None:
            action = "ClientAddDownload"
        self.downloads_status[download_id] = message
        status: str = message["status"]
        downloaded_bytes: int = message["downloaded_bytes"]
        progress: float = message["progress"]
        speed: float = message["speed"]
        remaining_bytes = download.size - downloaded_bytes
        if speed > 0:
            time_remaining = convert_time(int(remaining_bytes / speed))
        else:
            time_remaining = "INF"
        message = {
            "topic": "downloadclient",
            "action": action,
            "download_id": download.download_id,
            "filename": download.filename,
            "size": convert_size(download.size),
            "progress": f"{progress:>05.2%} {convert_size(downloaded_bytes)}",
            "status": status,
            "speed": f"{convert_size(speed)}",
            "remaining": f"{time_remaining}",
        }
        self.message_broker.send_message(message)

    def _process_message(self, message: Message) -> None:
        action: Optional[str] = message.get("action", None)
        if action is None:
            return
        download_id: int
        if action == "CreateDownload":
            url: str = message["url"]
            download_directory: str = message["download_directory"]
            self.create_download(url, download_directory)
        elif action == "StartDownload":
            download_id = message["download_id"]
            self.start_download(download_id)
        elif action == "DownloadInfo":
            download_id = message["download_id"]
            download_info: Dict[str, Any] = message["download_info"]
            self._receive_download_info(download_id, download_info)
        elif action == "DownloadStatus":
            self._send_client_download_status(message)

    def run(self) -> None:
        while True:
            self.subscriber.received.wait()
            for message in self.subscriber.messages():
                self._process_message(message)
