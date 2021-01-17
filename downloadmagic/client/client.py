from typing import Dict, cast

from downloadmagic.client.gui import ApplicationWindow, ListItem, choose_directory
from downloadmagic.config import ConfigOption, Configuration
from downloadmagic.download import Download, DownloadOperation, DownloadStatus
from downloadmagic.message import (
    CreateDownloadMessage,
    DownloadInfoMessage,
    DownloadOperationMessage,
    DownloadStatusMessage,
)
from downloadmagic.utilities import calculate_remaining_time, convert_size
from messaging import Message, MessageBroker, ThreadSubscriber


class DownloadClient:
    def __init__(
        self, message_broker: MessageBroker, configuration: Configuration
    ) -> None:
        self.message_broker = message_broker
        self.configuration = configuration
        self.application_window = ApplicationWindow(self._process_messages)
        self.downloads: Dict[int, Download] = {}
        self.downloads_status: Dict[int, DownloadStatusMessage] = {}
        self.subscriber = ThreadSubscriber({"downloadclient"})
        self.message_broker.subscribe(self.subscriber)
        self.download_directory = "."
        self._initialize()

    def _initialize(self) -> None:
        self._setup_button_commands()
        self._setup_binds()
        self._setup_menu()

    def start(self) -> None:
        """Start the client and the GUI."""
        self.application_window.start()

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
        download_list_area = self.application_window.download_list_area
        download_list = download_list_area.download_list
        selected_download = download_list.get_selected_item()
        if selected_download is None:
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

        The url for the download is taken from the input area in the
        GUI. If the download already exists, no action is taken.
        """
        input_area = self.application_window.download_input_area
        text = input_area.get_text()
        if not text:
            return
        input_area.clear_text()
        if self._download_exists(text):
            return
        message = CreateDownloadMessage(
            topic="downloadserver",
            action="CreateDownload",
            url=text,
            download_directory=self.download_directory,
        )
        self.message_broker.send_message(message)

    def remove_selected_download(self) -> None:
        """Remove the currently selected download.

        The download may only be removed if it has been completed,
        canceled, or it had an error. If no download is currently
        selected, no action is taken.
        """
        download_list_area = self.application_window.download_list_area
        download_list = download_list_area.download_list
        selected_download = download_list.get_selected_item()
        if selected_download is None:
            return
        status_message = self.downloads_status[selected_download]
        status = status_message["status"]
        if status in (
            DownloadStatus.COMPLETED.value,
            DownloadStatus.ERROR.value,
            DownloadStatus.CANCELED.value,
        ):
            del self.downloads[selected_download]
            del self.downloads_status[selected_download]
            download_list.delete_item(selected_download)

    def _setup_button_commands(self) -> None:
        download_list_area = self.application_window.download_list_area
        button_bar = download_list_area.button_bar
        bn = button_bar.ButtonName
        start_command = lambda: self.download_operation(DownloadOperation.START)
        pause_command = lambda: self.download_operation(DownloadOperation.PAUSE)
        cancel_command = lambda: self.download_operation(DownloadOperation.CANCEL)
        button_bar.set_button_command(bn.ADD_DOWNLOAD, self.create_download)
        button_bar.set_button_command(bn.START_DOWNLOAD, start_command)
        button_bar.set_button_command(bn.PAUSE_DOWNLOAD, pause_command)
        button_bar.set_button_command(bn.CANCEL_DOWNLOAD, cancel_command)
        button_bar.set_button_command(bn.REMOVE_DOWNLOAD, self.remove_selected_download)

    def _setup_binds(self) -> None:
        input_area = self.application_window.download_input_area
        input_area.set_text_entry_bind("<Return>", lambda event: self.create_download())

    def _setup_menu(self) -> None:
        application_menu = self.application_window.application_menu
        file_menu = application_menu.file_menu
        options_menu = application_menu.options_menu
        fme = file_menu.MenuEntry
        file_menu.set_menu_entry_command(fme.EXIT, self._stop_gui)
        file_menu.set_menu_entry_command(
            fme.SET_DOWNLOAD_DIRECTORY, self._set_download_directory
        )
        language_menu = options_menu.language_menu
        lme = language_menu.MenuEntry
        english_command = lambda: self._change_language("en")
        spanish_command = lambda: self._change_language("es")
        japanese_command = lambda: self._change_language("ja")
        language_menu.set_menu_entry_command(lme.ENGLISH, english_command)
        language_menu.set_menu_entry_command(lme.SPANISH, spanish_command)
        language_menu.set_menu_entry_command(lme.JAPANESE, japanese_command)

    def _stop_gui(self) -> None:
        self.application_window.stop = True

    def _set_download_directory(self) -> None:
        download_directory = choose_directory(self.application_window.root)
        if download_directory:
            self.download_directory = download_directory

    def _download_exists(self, url: str) -> bool:
        for download in self.downloads.values():
            if download.url == url:
                return True
        return False

    def _change_language(self, language: str) -> None:
        self.configuration.set_config_value(ConfigOption.LANGUAGE, language)
        self._reload_gui_text()

    def _reload_gui_text(self) -> None:
        input_area = self.application_window.download_input_area
        # There is no need to call reload_text() on the children of download_list_area
        # as it's reload_text() method already does that
        download_list_area = self.application_window.download_list_area
        application_menu = self.application_window.application_menu
        input_area.reload_text()
        download_list_area.reload_text()
        application_menu.reload_text()

    def _process_messages(self) -> None:
        for message in self.subscriber.messages():
            self._process_message(message)

    def _process_message(self, message: Message) -> None:
        action: str = message["action"]
        if action == "DownloadInfo":
            download_info_message = cast(DownloadInfoMessage, message)
            self._receive_download_info(download_info_message)
        elif action == "DownloadStatus":
            download_status_message = cast(DownloadStatusMessage, message)
            self._receive_download_status(download_status_message)

    def _receive_download_info(self, message: DownloadInfoMessage) -> None:
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

    def _get_download_from_download_info(
        self, message: DownloadInfoMessage
    ) -> Download:
        download = Download(
            download_id=message["download_id"],
            url=message["url"],
            download_directory=message["download_directory"],
            size=message["size"],
            filename=message["filename"],
            is_pausable=message["is_pausable"],
        )
        return download

    def _receive_download_status(self, message: DownloadStatusMessage) -> None:
        download_id: int = message["download_id"]
        download = self.downloads.get(download_id, None)
        if download is None:
            return
        self.downloads_status[download_id] = message
        remaining_bytes = download.size - message["downloaded_bytes"]
        list_item = ListItem(
            download_id=download_id,
            filename=download.filename,
            size=convert_size(download.size),
            progress=self._get_progress_from_download_status(message),
            status=message["status"],
            speed=f"{convert_size(message['speed'])}/s",
            remaining=calculate_remaining_time(message["speed"], remaining_bytes),
        )
        download_list = self.application_window.download_list_area.download_list
        download_list.update_item(list_item)

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
