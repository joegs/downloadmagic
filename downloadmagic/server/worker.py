import os
import threading as th

import requests
from downloadmagic.download import Download, DownloadOperation, DownloadStatus
from downloadmagic.utilities import Timer
from messaging import Message, MessageBroker, ThreadSubscriber


class DownloadWorker(th.Thread):
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
        self.download_id = download_id
        self.url = url
        self.download_directory = download_directory
        self.download: Download
        self.subscriber = ThreadSubscriber({f"downloadworker{self.download_id}"})
        self.downloaded_bytes = 0
        self.status = DownloadStatus.UNSTARTED
        self.speed: float = 0
        self.message_broker = message_broker
        self.message_broker.subscribe(self.subscriber)

    def run(self) -> None:
        self._initialize_download()
        while True:
            self.subscriber.received.wait()
            self._process_messsages()
            if (
                self.status == DownloadStatus.COMPLETED
                or self.status == DownloadStatus.CANCELED
            ):
                return

    def _initialize_download(self) -> None:
        self.download = Download.from_values(
            self.download_id, self.url, self.download_directory
        )
        message = {
            "topic": "downloadserver",
            "download_id": self.download_id,
            "download_info": self.download.to_dictionary(),
        }
        self.message_broker.send_message(message)

    def _process_messsages(self) -> None:
        for message in self.subscriber.messages():
            self._process_message(message)

    def _process_message(self, message: Message) -> None:
        operation = message.get("download_operation", None)
        if operation is None:
            return
        if operation == DownloadOperation.START.value and (
            self.status == DownloadStatus.UNSTARTED
            or self.status == DownloadStatus.PAUSED
        ):
            self._start_download()
        elif (
            operation == DownloadOperation.CANCEL.value
            and self.status != DownloadStatus.COMPLETED
        ):
            self.status = DownloadStatus.CANCELED
            self._send_download_status()
        elif (
            operation == DownloadOperation.PAUSE.value
            and self.status == DownloadStatus.IN_PROGRESS
        ):
            if self.download.is_pausable:
                self.status = DownloadStatus.PAUSED
                self._send_download_status()

    def _send_download_status(self) -> None:
        progress = self.downloaded_bytes / self.download.size
        message = {
            "topic": "downloadserver",
            "download_id": self.download.download_id,
            "status": self.status.value,
            "downloaded_bytes": self.downloaded_bytes,
            "progress": progress,
            "speed": self.speed,
        }
        self.message_broker.send_message(message)

    def _delete_file(self) -> None:
        filepath = self.download.filepath
        try:
            os.remove(filepath)
        except FileNotFoundError:
            pass

    def _start_download(self) -> None:
        mode = "wb"
        if self.status == DownloadStatus.PAUSED:
            range_header = f"bytes={self.downloaded_bytes}-{self.download.size}"
            response = requests.get(
                self.download.url, stream=True, headers={"Range": range_header}
            )
            mode = "ab"
        else:
            response = requests.get(self.download.url, stream=True)
        timer = Timer()
        timer.start()
        cycle_bytes = 0
        with open(self.download.filepath, mode) as file:
            self.status = DownloadStatus.IN_PROGRESS
            for chunk in response.iter_content(self.CHUNK_SIZE):
                file.write(chunk)
                self.downloaded_bytes += len(chunk)
                cycle_bytes += len(chunk)
                timer.measure()
                if (timer.elapsed_time) >= self.UPDATE_INTERVAL:
                    if self.downloaded_bytes == self.download.size:
                        break
                    self.speed = cycle_bytes / timer.elapsed_time
                    cycle_bytes = 0
                    self._process_messsages()
                    if self.status == DownloadStatus.CANCELED:
                        response.close()
                        file.close()
                        self._delete_file()
                        return
                    elif self.status == DownloadStatus.PAUSED:
                        response.close()
                        return
                    self._send_download_status()
                    timer.start()
        if self.downloaded_bytes != self.download.size:
            self.status = DownloadStatus.ERROR
        else:
            self.status = DownloadStatus.COMPLETED
        self._send_download_status()
