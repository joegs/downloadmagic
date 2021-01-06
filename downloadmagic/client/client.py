import sys
from typing import Dict, cast

from downloadmagic.client.gui import ApplicationWindow, ListItem, choose_directory
from downloadmagic.download import Download, DownloadOperation, DownloadStatus
from downloadmagic.message import (
    CreateDownloadMessage,
    DownloadInfoMessage,
    DownloadOperationMessage,
    DownloadStatusMessage,
)
from downloadmagic.utilities import convert_size, convert_time
from messaging import Message, MessageBroker, ThreadSubscriber


class DownloadClient:
    def __init__(self, message_broker: MessageBroker) -> None:
        self.application_window = ApplicationWindow(self._process_messages)
        self.downloads: Dict[int, Download] = {}
        self.downloads_status: Dict[int, DownloadStatusMessage] = {}
        self.subscriber = ThreadSubscriber({"downloadclient"})
        self.message_broker = message_broker
        self.message_broker.subscribe(self.subscriber)
        self.download_directory = "."
        self._initialize()

    def _initialize(self) -> None:
        button_bar = self.application_window.download_list_area.button_bar
        button_bar.add_download_button.configure(command=self.create_download)
        button_bar.start_download_button.configure(
            command=lambda: self.download_operation(DownloadOperation.START)
        )
        button_bar.pause_download_button.configure(
            command=lambda: self.download_operation(DownloadOperation.PAUSE)
        )
        button_bar.cancel_download_button.configure(
            command=lambda: self.download_operation(DownloadOperation.CANCEL)
        )
        self._setup_binds()
        self._setup_menu()

    def download_operation(self, download_operation: DownloadOperation) -> None:
        """Send a download operation message to the server.

        The `download_id` of the message corresponds to the currently
        selected download. If no download is currently selected, no
        action is taken.

        Parameters
        ----------
        download_operation : DownloadOperation
            The download operation for the message.
        """
        download_list = self.application_window.download_list_area.download_list
        selected_download = download_list.get_selected_item()
        # If there is no selected download
        if selected_download == -1:
            return
        message = DownloadOperationMessage(
            topic="downloadserver",
            action="DownloadOperation",
            download_id=selected_download,
            download_operation=download_operation.value,
        )
        self.message_broker.send_message(message)

    def create_download(self) -> None:
        """Send a create download message to the server.

        The url for the download is taken from the input area in
        the GUI.
        """
        input_area = self.application_window.download_input_area
        text = input_area.get_text()
        if not text:
            return
        input_area.clear_text()
        message = CreateDownloadMessage(
            topic="downloadserver",
            action="CreateDownload",
            url=text,
            download_directory=self.download_directory,
        )
        self.message_broker.send_message(message)

    def _setup_binds(self) -> None:
        input_area = self.application_window.download_input_area
        input_area.text_entry.bind("<Return>", lambda event: self.create_download())

    def _setup_menu(self) -> None:
        application_menu = self.application_window.application_menu
        file_menu = application_menu.file_menu
        file_menu.set_exit_command(sys.exit)
        file_menu.set_download_directory_command(self._set_download_directory)

    def _set_download_directory(self) -> None:
        download_directory = choose_directory(self.application_window.root)
        if download_directory:
            self.download_directory = download_directory

    def _calculate_remaining_time(self, speed: float, remaining_bytes: float) -> str:
        """Return the download remaining time, as a readable string.

        Parameters
        ----------
        speed : float
            The download speed, in bytes per second.
        remaining_bytes : float
            The remaining bytes of the download.

        Returns
        -------
        str
            The remaining time of the download, as a human readable
            string.
        """
        remaining_time = ""
        if speed > 0:
            seconds = int(remaining_bytes / speed)
            remaining_time = convert_time(seconds)
        return remaining_time

    def _get_progress_from_download_status(self, message: DownloadStatusMessage) -> str:
        """Return a progress string calculated from a download status.

        Parameters
        ----------
        message : DownloadStatusMessage
            The download status message to create the string from.

        Returns
        -------
        str
            The download progress, in the format "XX.X% XX.X (U)B",
            where U is the appropiate human readable byte unit.
        """
        percentage = f"{message['progress']:>.2%} "
        size = f"{convert_size(message['downloaded_bytes'])}"
        progress = percentage + size
        return progress

    def _get_download_from_download_info(
        self, message: DownloadInfoMessage
    ) -> Download:
        """Return a download created from a download info message.

        Parameters
        ----------
        message : DownloadInfoMessage
            The download info message to create the download from.

        Returns
        -------
        Download
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
        return download

    def _receive_download_status(self, message: DownloadStatusMessage) -> None:
        """Receive a download status message.

        The contents of the message will be used to update the download
        list in the GUI.

        Parameters
        ----------
        message : DownloadStatusMessage
        """
        download_id: int = message["download_id"]
        download = self.downloads.get(download_id, None)
        if download is None:
            return
        remaining_bytes = download.size - message["downloaded_bytes"]
        list_item = ListItem(
            download_id=download_id,
            filename=download.filename,
            size=convert_size(download.size),
            progress=self._get_progress_from_download_status(message),
            status=message["status"],
            speed=f"{convert_size(message['speed'])}/s",
            remaining=self._calculate_remaining_time(message["speed"], remaining_bytes),
        )
        download_list = self.application_window.download_list_area.download_list
        download_list.update_item(list_item)

    def _receive_download_info(self, message: DownloadInfoMessage) -> None:
        """Receive a download info message.

        The contents of the message will be used to update the download
        list in the GUI.

        Parameters
        ----------
        message : DownloadInfoMessage
        """
        download_id: int = message["download_id"]
        if download_id in self.downloads:
            return
        download = self._get_download_from_download_info(message)
        self.downloads[download_id] = download
        list_item = ListItem(
            download_id=download_id,
            filename=message["filename"],
            size=convert_size(message["size"]),
            progress="0.00% 0.00 B",
            status=DownloadStatus.UNSTARTED.value,
            speed="0.00 B/s",
            remaining="",
        )
        download_list = self.application_window.download_list_area.download_list
        download_list.update_item(list_item)

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
        """Start the client and the GUI."""
        self.application_window.start()
