import importlib.resources
import tkinter as tk
from enum import Enum, auto
from functools import partial
from tkinter import filedialog, ttk
from typing import Callable, Dict, NamedTuple, Optional, Union

from downloadmagic.download import DownloadStatus


def choose_directory(parent: Union[tk.Widget, tk.Tk]) -> str:
    directory: Optional[str] = filedialog.askdirectory(
        parent=parent, title="Choose a Directory", initialdir=".", mustexist=True
    )
    if directory is None:
        return ""
    return directory


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

    def clear_text(self) -> None:
        self.text_entry.delete(0, tk.END)

    def set_text_entry_bind(
        self,
        binding: str,
        function: Callable[[tk.Event], None],
    ) -> None:
        self.text_entry.bind(binding, function)


class DownloadListButtonBar(GuiElement):
    """A button bar used to control downloads."""

    class ButtonName(Enum):
        ADD_DOWNLOAD = auto()
        START_DOWNLOAD = auto()
        PAUSE_DOWNLOAD = auto()
        CANCEL_DOWNLOAD = auto()
        REMOVE_DOWNLOAD = auto()

    def __init__(self, parent: Union[tk.Widget, tk.Tk]):
        super().__init__(parent)
        self.buttons: Dict[DownloadListButtonBar.ButtonName, ttk.Button] = {}
        self._initialize()

    def _initialize(self) -> None:
        bn = self.ButtonName
        self.buttons[bn.ADD_DOWNLOAD] = ttk.Button(self, text="Add")
        self.buttons[bn.START_DOWNLOAD] = ttk.Button(self, text="Start / Resume")
        self.buttons[bn.PAUSE_DOWNLOAD] = ttk.Button(self, text="Pause")
        self.buttons[bn.CANCEL_DOWNLOAD] = ttk.Button(self, text="Cancel")
        self.buttons[bn.REMOVE_DOWNLOAD] = ttk.Button(self, text="Remove")

        for index, button in enumerate(self.buttons.values()):
            button.grid(column=index, row=0, padx="0 10")

    def set_button_command(
        self,
        button_name: "DownloadListButtonBar.ButtonName",
        command: Callable[[], None],
    ) -> None:
        self.buttons[button_name].configure(command=command)


class ListItem(NamedTuple):
    """Schema for a download list item.

    Every attribute of this class corresponds to the columns of
    the download list.
    """

    download_id: int
    filename: str
    size: str
    progress: str
    status: str
    speed: str
    remaining: str


class DownloadList(GuiElement):
    """An area where downloads are displayed in a list.

    The first column of COLUMNS, the ID for the downloads, is not
    displayed. It's used to identify specific downloads.

    """

    COLUMNS = ("ID", "Filename", "Size", "Progress", "Status", "Speed", "Remaining")
    STATUS_COLORS = {
        DownloadStatus.COMPLETED.value: "#ccffcc",
        DownloadStatus.IN_PROGRESS.value: "#ccebff",
        DownloadStatus.PAUSED.value: "#ffffcc",
        DownloadStatus.CANCELED.value: "#ffe0b3",
        DownloadStatus.ERROR.value: "#ffcccc",
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
        self._configure_tree()
        self.tree.grid(column=0, row=0, sticky="NSWE")
        self.vscrollbar.grid(column=1, row=0, sticky="NS")
        self.hscrollbar.grid(column=0, row=1, sticky="WE")

    def _configure_tree(self) -> None:
        self.tree.bind("<Key-Escape>", lambda event: self.deselect_current_item())
        self.tree.configure(
            columns=self.COLUMNS,
            show="headings",
            displaycolumns=self.COLUMNS[1:],
            xscrollcommand=self.hscrollbar.set,
            yscrollcommand=self.vscrollbar.set,
        )
        for tag, color in self.STATUS_COLORS.items():
            self.tree.tag_configure(tag, background=color)
        for index, column in enumerate(self.COLUMNS):
            self.tree.heading(
                column, text=column, command=partial(self._sort_column, index)
            )
            self.tree.column(column, minwidth=200)

    def _sort_column(self, column_index: int) -> None:
        """Sort the list items by the selected column.

        Parameters
        ----------
        column_index : int
            The index of the column to use as reference for sorting.
        """
        items = [
            (self.tree.set(iid, column_index), iid)
            for iid in self.tree.get_children("")
        ]
        items.sort()
        for index, (_, iid) in enumerate(items):
            self.tree.move(iid, "", index)

    def _get_item_iid(self, download_id: int) -> str:
        """Return the iid of the item with the specified download id.

        The iid is the unique identifier for each item (row) in the
        `TreeView`.

        Parameters
        ----------
        download_id : int
            The download id of the item whose iid will be retrieved.

        Returns
        -------
        str
            The iid of the item. If the item is not present of the
            list, this value is an empty string.
        """
        for i in self.tree.get_children(""):
            iid: str = i
            value = self.tree.set(iid, 0)
            if int(value) == download_id:
                return iid
        return ""

    def deselect_current_item(self) -> None:
        """Deselect the currently selected item."""
        selection = self.tree.selection()
        if selection:
            self.tree.selection_remove(selection[0])

    def get_selected_item(self) -> Optional[int]:
        """Return the download ID of the currently selected item.

        Returns
        -------
        Optional[int]
            The download id corresponding to the currently selected
            item. If no item is selected, this value is -1.
        """
        selection = self.tree.selection()
        download_id = None
        if selection:
            download_id = int(self.tree.set(selection[0], 0))
        return download_id

    def update_item(self, list_item: ListItem) -> None:
        """Update a download item on the list.

        If the item was not already on the list, it's added to it.

        Parameters
        ----------
        list_item : ListItem
            The download item to update on the list.
        """
        iid = self._get_item_iid(list_item.download_id)
        values = (
            f"{list_item.download_id}",
            list_item.filename,
            list_item.size,
            list_item.progress,
            list_item.status,
            list_item.speed,
            list_item.remaining,
        )
        tag = list_item.status
        # Item is already on the list, update it
        if iid:
            self.tree.item(iid, values=values, tags=tag)
        # Item is not on the list, add it
        else:
            self.tree.insert("", "end", values=values, tags=tag)

    def delete_item(self, download_id: int) -> None:
        """Delete a download item from the list.

        If the item is not on the list, no action is taken.

        Parameters
        ----------
        download_id : int
            The id of the download item to delete.
        """
        iid = self._get_item_iid(download_id)
        if iid:
            self.tree.delete(iid)


class DownloadListArea(GuiElement):
    def __init__(self, parent: Union[tk.Widget, tk.Tk]):
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


class FileMenu(tk.Menu):
    def __init__(self, menubutton: ttk.Menubutton) -> None:
        super().__init__(menubutton, tearoff=False)
        self._initialize()

    def _initialize(self) -> None:
        self.add_command(label="Set Download Directory")
        self.add_command(label="Exit")

    def set_download_directory_command(self, command: Callable[[], None]) -> None:
        self.entryconfigure(0, command=command)

    def set_exit_command(self, command: Callable[[], None]) -> None:
        self.entryconfigure(1, command=command)


class ApplicationMenu(GuiElement):
    def __init__(self, parent: Union[tk.Widget, tk.Tk]):
        super().__init__(parent)
        self.file_button = ttk.Menubutton(self, text="File", takefocus=False)
        self.file_menu = FileMenu(self.file_button)
        self._initialize()

    def _initialize(self) -> None:
        self.file_button.grid(column=0, row=0)
        self.file_button.configure(menu=self.file_menu)


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
        self.application_menu = ApplicationMenu(self.root)
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
        self.root.rowconfigure(2, weight=1)
        self.application_menu.grid(column=0, row=0, sticky="WE")
        self.download_input_area.grid(column=0, row=1, sticky="NSWE")
        self.download_list_area.grid(column=0, row=2, sticky="NSWE")
        # self._load_icon()

    def _load_icon(self) -> None:
        """Load the icon for the main window."""
        path = importlib.resources.path("downloadmagic", "icon.ico")
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
