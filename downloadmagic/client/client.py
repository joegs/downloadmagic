from typing import Optional

from downloadmagic.client.gui import ApplicationWindow
from messaging import ThreadSubscriber, MessageBroker, Message


class Client:
    def __init__(self, message_broker: MessageBroker) -> None:
        self.application_window = ApplicationWindow(self._process_messages)
        self.subscriber = ThreadSubscriber({"downloadclient"})
        self.message_broker = message_broker
        self.message_broker.subscribe(self.subscriber)
        self._initialize()

    def _initialize(self) -> None:
        button_bar = self.application_window.download_list_area.button_bar
        button_bar.add_download_button.configure(command=self._create_download)
        button_bar.start_download_button.configure(command=self._start_download)

    def _start_download(self) -> None:
        download_list = self.application_window.download_list_area.download_list
        selected_download = download_list.get_selected_item()
        if selected_download == -1:
            return
        message = {
            "topic": "downloadserver",
            "action": "StartDownload",
            "download_id": selected_download,
        }
        self.message_broker.send_message(message)

    def _create_download(self) -> None:
        input_area = self.application_window.download_input_area
        text = input_area.get_text()
        if not text:
            return
        message = {
            "topic": "downloadserver",
            "action": "CreateDownload",
            "url": text,
            "download_directory": ".",
        }
        self.message_broker.send_message(message)

    def _create_download_item(self, message: Message) -> None:
        download_list = self.application_window.download_list_area.download_list
        filename: str = message["filename"]
        size: str = message["size"]
        progress: str = message["progress"]
        status: str = message["status"]
        speed: str = message["speed"]
        remaining: str = message["remaining"]
        values = (
            filename,
            size,
            progress,
            status,
            speed,
            remaining,
        )
        download_list.add_item(message["download_id"], values)

    def _update_download_item(self, message: Message) -> None:
        download_list = self.application_window.download_list_area.download_list
        filename: str = message["filename"]
        size: str = message["size"]
        progress: str = message["progress"]
        status: str = message["status"]
        speed: str = message["speed"]
        remaining: str = message["remaining"]
        values = (
            filename,
            size,
            progress,
            status,
            speed,
            remaining,
        )
        download_list.update_item(message["download_id"], values)

    def _process_message(self, message: Message) -> None:
        action: Optional[str] = message.get("action", None)
        if action is None:
            return
        if action == "ClientAddDownload":
            self._create_download_item(message)
        if action == "ClientUpdateDownload":
            self._update_download_item(message)

    def _process_messages(self) -> None:
        for message in self.subscriber.messages():
            self._process_message(message)

    def start(self) -> None:
        self.application_window.start()
