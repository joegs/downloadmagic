import importlib.resources
import tkinter as tk
from functools import partial
from tkinter import ttk
from typing import Callable, Tuple, Union

from downloadmagic.download import DownloadStatus


class GuiElement(ttk.Frame):
    """Base class for all GUI elements."""

    def _initialize(self) -> None:
        pass


class DownloadInputArea(GuiElement):
    """An area where download links are inputted by the user."""

    def __init__(self, parent: Union[tk.Widget, tk.Tk]):
        super().__init__(parent)
        self.label = ttk.Label(self, text="Download link")
        self.text_entry = ttk.Entry(self, width=100)
        self._initialize()

    def _initialize(self) -> None:
        self.configure(padding=10)
        self.label.grid(column=0, row=0, padx="0 10", pady="0 10", sticky="NSW")
        self.text_entry.grid(column=1, row=0, pady="0 10", sticky="WE")

    def get_text(self) -> str:
        text: str = self.text_entry.get()
        return text


class DownloadListButtonBar(GuiElement):
    """A button bar used to control downloads."""

    def __init__(self, parent: Union[tk.Widget, tk.Tk]):
        super().__init__(parent)
        self.add_download_button = ttk.Button(self, text="Add")
        self.start_download_button = ttk.Button(self, text="Start / Resume")
        self.pause_download_button = ttk.Button(self, text="Pause")
        self.cancel_download_button = ttk.Button(self, text="Cancel")
        self._initialize()

    def _initialize(self) -> None:
        self.add_download_button.grid(column=0, row=0, padx="0 10")
        self.start_download_button.grid(column=1, row=0, padx="0 10")
        self.pause_download_button.grid(column=2, row=0, padx="0 10")
        self.cancel_download_button.grid(column=3, row=0, padx="0 10")


class DownloadList(GuiElement):
    """An area where downloads are displayed in a list.

    The first column of COLUMNS, the ID for the downloads, is not
    displayed. It's used to identify specific downloads.

    """

    COLUMNS = ("ID", "Filename", "Size", "Progress", "Status", "Speed", "Remaining")
    TAG_COLORS = {
        "completed": "#ccffcc",
        "in_progress": "#ccebff",
        "paused": "#ffffcc",
        "canceled": "#ffcccc",
    }
    _STATUS_TAG_MAP = {
        DownloadStatus.COMPLETED.name: "completed",
        DownloadStatus.IN_PROGRESS.name: "in_progress",
        DownloadStatus.PAUSED.name: "paused",
        DownloadStatus.CANCELED.name: "canceled",
        DownloadStatus.UNSTARTED.name: "unstarted",
    }

    def __init__(self, parent: Union[tk.Widget, tk.Tk]):
        super().__init__(parent)
        self.tree = ttk.Treeview(self)
        self.hscrollbar = ttk.Scrollbar(
            self, orient=tk.HORIZONTAL, command=self.tree.xview
        )
        self.vscrollbar = ttk.Scrollbar(self, command=self.tree.yview)
        self._initialize()

    def _initialize(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.tree.configure(
            columns=self.COLUMNS,
            show="headings",
            displaycolumns=tuple(self.COLUMNS[1:]),
            xscrollcommand=self.hscrollbar.set,
            yscrollcommand=self.vscrollbar.set,
        )
        self.tree.bind("<Key-Escape>", lambda event: self.deselect_current_item())
        self._configure_tag_colors()
        for index, column in enumerate(self.COLUMNS):
            self.tree.heading(
                column, text=column, command=partial(self._sort_column, index)
            )
            self.tree.column(column, minwidth=200)
        self.tree.grid(column=0, row=0, sticky="NSWE")
        self.vscrollbar.grid(column=1, row=0, sticky="NS")
        self.hscrollbar.grid(column=0, row=1, sticky="WE")

    def _configure_tag_colors(self) -> None:
        for tag, color in self.TAG_COLORS.items():
            self.tree.tag_configure(tag, background=color)

    def _sort_column(self, column_index: int) -> None:
        items = [
            (self.tree.set(iid, column_index), iid)
            for iid in self.tree.get_children("")
        ]
        items.sort()
        for index, (_, iid) in enumerate(items):
            self.tree.move(iid, "", index)

    def _get_item_iid(self, download_id: int) -> str:
        for i in self.tree.get_children(""):
            iid: str = i
            value = self.tree.set(iid, 0)
            if int(value) == download_id:
                return iid
        return ""

    def deselect_current_item(self) -> None:
        """Deselect the current item."""
        selection = self.tree.selection()
        if selection:
            self.tree.selection_remove(selection[0])

    def get_selected_item(self) -> int:
        """Return the download ID of the currently selected item.

        Returns
        -------
        int
            The download id corresponding to the currently selected
            item. If no item is selected, this value is -1.
        """
        selection = self.tree.selection()
        download_id = -1
        if selection:
            download_id = self.tree.set(selection[0], 0)
        return download_id

    def update_item(self, download_id: int, values: Tuple[str, ...]) -> None:
        """Update a download item on the list.

        If the item was not already on the list, it's added to it.

        Parameters
        ----------
        download_id : int
            The id of the download item to update.
        values : Tuple[str, ...]
            The values of the item. They should be in the same order
            as the `COLUMNS` attribute.
        """
        iid = self._get_item_iid(download_id)
        status = values[3]
        values = (f"{download_id}",) + values
        tag = self._STATUS_TAG_MAP.get(status, "unstarted")
        # Item is already on the list, update it
        if iid:
            self.tree.item(iid, values=values, tags=tag)
        # Item is not on the list, add it
        else:
            self.tree.insert("", "end", values=values, tags=tag)

    def delete_item(self, download_id: int) -> None:
        """Delete a download item from the list.

        Parameters
        ----------
        download_id : int
            The id of the download item to delete.
        """
        iid = self._get_item_iid(download_id)
        if iid:
            self.tree.delete(iid)


class DownloadListArea(GuiElement):
    def __init__(
        self,
        parent: Union[tk.Widget, tk.Tk],
    ):
        super().__init__(parent)
        self.button_bar = DownloadListButtonBar(self)
        self.download_list = DownloadList(self)
        self._initialize()

    def _initialize(self) -> None:
        self.configure(padding=10)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.button_bar.grid(column=0, row=0, sticky="WE", pady="0 10")
        self.download_list.grid(column=0, row=1, sticky="NSWE")


class ApplicationWindow:
    """The container for the main window.

    Parameters
    ----------
    update_function : Callable[[], None]
        A function that will be called periodically, around 100 times
        per second. This should be a function that needs to execute
        constantly on the main thread.

    """

    def __init__(self, update_function: Callable[[], None]) -> None:
        self.root = tk.Tk()
        self.root.title("Download Manager")
        self.update_function = update_function
        self._fix_treeview_tags()
        self.download_input_area = DownloadInputArea(self.root)
        self.download_list_area = DownloadListArea(self.root)
        self._initialize()

    def start(self) -> None:
        """Start the main window and the Tk mainloop."""
        self._periodic_refresh()
        self.root.mainloop()

    def _initialize(self) -> None:
        self.root.minsize(960, 540)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        self.download_input_area.grid(column=0, row=0, sticky="NSWE")
        self.download_list_area.grid(column=0, row=1, sticky="NSWE")
        # self._load_icon()

    def _load_icon(self) -> None:
        path = importlib.resources.path("downloadmanager", "icon.ico")
        with path as file:
            self.root.iconbitmap(file)

    def _periodic_refresh(self) -> None:
        self.update_function()
        self.root.after(1000 // 100, self._periodic_refresh)

    def _fix_treeview_tags(self) -> None:
        """Fixes a bug with treeview in python >= 3.7.3

        See https://bugs.python.org/issue36468 for more info
        """

        def fixed_map(option):  # type: ignore
            # Fix for setting text colour for Tkinter 8.6.9
            # From: https://core.tcl.tk/tk/info/509cafafae
            #
            # Returns the style map for 'option' with any styles starting with
            # ('!disabled', '!selected', ...) filtered out.

            # style.map() returns an empty list for missing options, so this
            # should be future-safe.
            return [
                elm
                for elm in style.map("Treeview", query_opt=option)
                if elm[:2] != ("!disabled", "!selected")
            ]

        style = ttk.Style()
        style.map(
            "Treeview",
            foreground=fixed_map("foreground"),
            background=fixed_map("background"),
        )
