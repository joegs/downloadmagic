from typing import Dict, cast

from downloadmagic.client.gui import ApplicationWindow
from downloadmagic.download import Download, DownloadOperation, DownloadStatus
from downloadmagic.message import (
    CreateDownloadMessage,
    DownloadInfoMessage,
    DownloadOperationMessage,
    DownloadStatusMessage,
)
from downloadmagic.utilities import convert_size, convert_time
from messaging import Message, MessageBroker, ThreadSubscriber


class Client:
    def __init__(self, message_broker: MessageBroker) -> None:
        self.application_window = ApplicationWindow(self._process_messages)
        self.downloads: Dict[int, Download] = {}
        self.downloads_status: Dict[int, DownloadStatusMessage] = {}
        self.subscriber = ThreadSubscriber({"downloadclient"})
        self.message_broker = message_broker
        self.message_broker.subscribe(self.subscriber)
        self._initialize()

    def _initialize(self) -> None:
        button_bar = self.application_window.download_list_area.button_bar
        button_bar.add_download_button.configure(command=self._create_download)
        button_bar.start_download_button.configure(
            command=lambda: self._download_operation(DownloadOperation.START)
        )
        button_bar.pause_download_button.configure(
            command=lambda: self._download_operation(DownloadOperation.PAUSE)
        )
        button_bar.cancel_download_button.configure(
            command=lambda: self._download_operation(DownloadOperation.CANCEL)
        )

    def _download_operation(self, download_operation: DownloadOperation) -> None:
        download_list = self.application_window.download_list_area.download_list
        selected_download = download_list.get_selected_item()
        if selected_download == -1:
            return
        message = DownloadOperationMessage(
            topic="downloadserver",
            action="DownloadOperation",
            download_id=selected_download,
            download_operation=download_operation.value,
        )
        self.message_broker.send_message(message)

    def _create_download(self) -> None:
        input_area = self.application_window.download_input_area
        text = input_area.get_text()
        if not text:
            return
        message = CreateDownloadMessage(
            topic="downloadserver",
            action="CreateDownload",
            url=text,
            download_directory=".",
        )
        self.message_broker.send_message(message)

    def _receive_download_status(self, message: DownloadStatusMessage) -> None:
        download_id: int = message["download_id"]
        download = self.downloads.get(download_id, None)
        if download is None:
            return
        remaining_bytes = download.size - message["downloaded_bytes"]
        filename: str = download.filename
        size: str = convert_size(download.size)
        progress: str = (
            f"{message['progress']:>.2%} {convert_size(message['downloaded_bytes'])}"
        )
        status: str = message["status"]
        speed: str = convert_size(message["speed"])
        if message["speed"] > 0:
            seconds = int(remaining_bytes / message["speed"])
            remaining_time = convert_time(seconds)
        else:
            remaining_time = ""
        values = (
            filename,
            size,
            progress,
            status,
            speed,
            remaining_time,
        )
        download_list = self.application_window.download_list_area.download_list
        download_list.update_item(download_id, values)

    def _receive_download_info(self, message: DownloadInfoMessage) -> None:
        download_id: int = message["download_id"]
        if download_id in self.downloads:
            return
        download = Download(
            download_id=message["download_id"],
            url=message["url"],
            download_directory=message["download_directory"],
            size=message["size"],
            filename=message["filename"],
            filepath=message["filepath"],
            is_pausable=message["is_pausable"],
        )
        self.downloads[download_id] = download
        values = (
            message["filename"],
            convert_size(message["size"]),
            "0.00 B",
            DownloadStatus.UNSTARTED.value,
            "0.00 B",
            "",
        )
        download_list = self.application_window.download_list_area.download_list
        download_list.add_item(download_id, values)

    def _process_message(self, message: Message) -> None:
        action: str = message["action"]
        if action == "DownloadInfo":
            download_info_message = cast(DownloadInfoMessage, message)
            self._receive_download_info(download_info_message)
        elif action == "DownloadStatus":
            download_status_message = cast(DownloadStatusMessage, message)
            self._receive_download_status(download_status_message)

    def _process_messages(self) -> None:
        for message in self.subscriber.messages():
            self._process_message(message)

    def start(self) -> None:
        self.application_window.start()
