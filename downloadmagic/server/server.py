import threading as th
from typing import Dict

from downloadmagic.download import Download, DownloadOperation, DownloadStatus
from downloadmagic.server.worker import DownloadWorker
from messaging import Message, MessageBroker, ThreadSubscriber


class DownloadServer(th.Thread):
    def __init__(self, message_broker: MessageBroker) -> None:
        super().__init__(daemon=True)
        self.downloads: Dict[int, Download]
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

    def _process_message(self, message: Message) -> None:
        pass

    def run(self) -> None:
        while True:
            self.subscriber.received.wait()
            for message in self.subscriber.messages():
                self._process_message(message)
