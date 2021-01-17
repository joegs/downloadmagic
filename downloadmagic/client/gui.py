import importlib.resources
import tkinter as tk
from abc import ABC, abstractmethod
from enum import Enum, auto
from functools import partial
from tkinter import filedialog, ttk
from typing import Callable, Dict, List, NamedTuple, Optional, Tuple, Union

from downloadmagic.download import DownloadStatus
from downloadmagic.translation import T_, TM_


def choose_directory(parent: Union[tk.Widget, tk.Tk]) -> str:
    """Prompt the user to choose a directory and return it.

    Parameters
    ----------
    parent : Union[tk.Widget, tk.Tk]
        The parent widget of the directory pick dialog.

    Returns
    -------
    str
        A string with the path of the directory chosen. If no directory
        was chosen, this string is empty.
    """
    directory: Optional[str] = filedialog.askdirectory(
        parent=parent,
        title="Choose a Directory",
        initialdir=".",
        mustexist=True,
    )
    if directory is None:
        return ""
    return directory


class GuiElement(ttk.Frame, ABC):
    """Base class for all GUI elements."""

    def _initialize(self) -> None:
        pass

    @abstractmethod
    def reload_text(self) -> None:
        ...


class MenuEntry(Enum):
    ...


class GuiMenu(tk.Menu, ABC):
    def set_menu_entry_command(
        self,
        menu_entry: MenuEntry,
        command: Callable[[], None],
    ) -> None:
        self.entryconfigure(menu_entry.value, command=command)

    @abstractmethod
    def reload_text(self) -> None:
        ...


class DownloadInputArea(GuiElement):
    """An area where download links are inputted by the user."""

    def __init__(self, parent: Union[tk.Widget, tk.Tk]):
        super().__init__(parent)
        self._label = ttk.Label(self)
        self._text_entry = ttk.Entry(self, width=100)
        self._initialize()

    def _initialize(self) -> None:
        self.configure(padding=10)
        self._label.grid(column=0, row=0, padx="0 10", pady="0 10", sticky="NSW")
        self._text_entry.grid(column=1, row=0, pady="0 10", sticky="WE")
        self.reload_text()

    def get_text(self) -> str:
        text: str = self._text_entry.get()
        return text

    def clear_text(self) -> None:
        self._text_entry.delete(0, tk.END)

    def set_text_entry_bind(
        self,
        binding: str,
        function: Callable[[tk.Event], None],
    ) -> None:
        self._text_entry.bind(binding, function)

    def reload_text(self) -> None:
        self._label.configure(text=T_("Download link"))


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
        self._buttons: Dict[DownloadListButtonBar.ButtonName, ttk.Button] = {}
        self._initialize()

    def _initialize(self) -> None:
        for button_name in self.ButtonName:
            self._buttons[button_name] = ttk.Button(self)
        for index, button in enumerate(self._buttons.values()):
            button.grid(column=index, row=0, padx="0 10")
        self.reload_text()

    def set_button_command(
        self,
        button_name: "DownloadListButtonBar.ButtonName",
        command: Callable[[], None],
    ) -> None:
        self._buttons[button_name].configure(command=command)

    def reload_text(self) -> None:
        bn = self.ButtonName
        buttons = {
            bn.ADD_DOWNLOAD: T_("Add"),
            bn.START_DOWNLOAD: T_("Start / Resume"),
            bn.PAUSE_DOWNLOAD: T_("Pause"),
            bn.CANCEL_DOWNLOAD: T_("Cancel"),
            bn.REMOVE_DOWNLOAD: T_("Remove"),
        }
        for button_name, button_text in buttons.items():
            self._buttons[button_name].configure(text=button_text)


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

    COLUMNS = (
        "ID",
        TM_("Filename"),
        TM_("Size"),
        TM_("Progress"),
        TM_("Status"),
        TM_("Speed"),
        TM_("Remaining"),
    )
    STATUS_COLORS = {
        DownloadStatus.COMPLETED.value: "#ccffcc",
        DownloadStatus.IN_PROGRESS.value: "#ccebff",
        DownloadStatus.PAUSED.value: "#ffffcc",
        DownloadStatus.CANCELED.value: "#ffe0b3",
        DownloadStatus.ERROR.value: "#ffcccc",
    }

    def __init__(self, parent: Union[tk.Widget, tk.Tk]):
        super().__init__(parent)
        self._tree = ttk.Treeview(self)
        self._hscrollbar = ttk.Scrollbar(
            self, orient=tk.HORIZONTAL, command=self._tree.xview
        )
        self._vscrollbar = ttk.Scrollbar(self, command=self._tree.yview)
        self._initialize()

    def _initialize(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self._configure_tree()
        self._tree.grid(column=0, row=0, sticky="NSWE")
        self._vscrollbar.grid(column=1, row=0, sticky="NS")
        self._hscrollbar.grid(column=0, row=1, sticky="WE")
        self.reload_text()

    def get_selected_item(self) -> Optional[int]:
        """Return the download ID of the currently selected item.

        Returns
        -------
        Optional[int]
            The download id corresponding to the currently selected
            item. If no item is selected, this value is -1.
        """
        selection = self._tree.selection()
        download_id = None
        if selection:
            download_id = int(self._tree.set(selection[0], 0))
        return download_id

    def deselect_current_item(self) -> None:
        """Deselect the currently selected item."""
        selection = self._tree.selection()
        if selection:
            self._tree.selection_remove(selection[0])

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
            self._tree.item(iid, values=values, tags=tag)
        # Item is not on the list, add it
        else:
            self._tree.insert("", "end", values=values, tags=tag)

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
            self._tree.delete(iid)

    def _configure_tree(self) -> None:
        self._tree.bind("<Key-Escape>", lambda event: self.deselect_current_item())
        self._tree.configure(
            columns=self.COLUMNS,
            show="headings",
            xscrollcommand=self._hscrollbar.set,
            yscrollcommand=self._vscrollbar.set,
        )
        for index, _ in enumerate(self.COLUMNS):
            self._tree.heading(index, command=partial(self._sort_column, index))
            self._tree.column(index, minwidth=200)
        for tag, color in self.STATUS_COLORS.items():
            self._tree.tag_configure(tag, background=color)

    def _sort_column(self, column_index: int) -> None:
        """Sort the list items by the selected column.

        Parameters
        ----------
        column_index : int
            The index of the column to use as reference for sorting.
        """
        items: List[Tuple[str, str]] = [
            (self._tree.set(iid, column_index), iid)
            for iid in self._tree.get_children("")
        ]
        items.sort()
        for index, (_, iid) in enumerate(items):
            self._tree.move(iid, "", index)

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
        for i in self._tree.get_children(""):
            iid: str = i
            value = self._tree.set(iid, 0)
            if int(value) == download_id:
                return iid
        return ""

    def reload_text(self) -> None:
        columns = [T_(column) for column in self.COLUMNS]
        self._tree.configure(columns=columns, displaycolumns=columns[1:])
        for index, column in enumerate(columns):
            self._tree.heading(index, text=column)
            self._tree.column(index, minwidth=200)


class DownloadListArea(GuiElement):
    """Container for `DownloadList` and `DownloadListButtonBar`."""

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

    def reload_text(self) -> None:
        self.button_bar.reload_text()
        self.download_list.reload_text()


class FileMenu(GuiMenu):
    class FileMenuEntry(MenuEntry):
        EXIT = 0

    def __init__(self, menubutton: ttk.Menubutton) -> None:
        super().__init__(menubutton, tearoff=False)
        self._initialize()

    def _initialize(self) -> None:
        for _ in self.FileMenuEntry:
            self.add_command()
        self.reload_text()

    def reload_text(self) -> None:
        me = self.FileMenuEntry
        entries = {
            me.EXIT: T_("Exit"),
        }
        for entry, text in entries.items():
            self.entryconfigure(entry.value, label=text)


class LanguageMenu(GuiMenu):
    class LanguageMenuEntry(MenuEntry):
        ENGLISH = 0
        SPANISH = 1
        JAPANESE = 2

    def __init__(self) -> None:
        super().__init__(tearoff=False)
        self._initialize()

    def _initialize(self) -> None:
        for _ in self.LanguageMenuEntry:
            self.add_command()
        self.reload_text()

    def reload_text(self) -> None:
        me = self.LanguageMenuEntry
        entries = {
            me.ENGLISH: T_("English"),
            me.SPANISH: T_("Spanish"),
            me.JAPANESE: T_("Japanese"),
        }
        for entry, text in entries.items():
            self.entryconfigure(entry.value, label=text)


class OptionMenu(GuiMenu):
    class OptionMenuEntry(MenuEntry):
        LANGUAGE = 0
        SET_DOWNLOAD_DIRECTORY = 1

    def __init__(self, menubutton: ttk.Menubutton) -> None:
        super().__init__(menubutton, tearoff=False)
        self.language_menu = LanguageMenu()
        self._initialize()

    def _initialize(self) -> None:
        me = self.OptionMenuEntry
        menu_types = {
            me.LANGUAGE: "cascade",
            me.SET_DOWNLOAD_DIRECTORY: "command",
        }
        for _, menu_type in menu_types.items():
            self.add(menu_type)
        self.entryconfigure(me.LANGUAGE.value, menu=self.language_menu)
        self.reload_text()

    def reload_text(self) -> None:
        me = self.OptionMenuEntry
        entries = {
            me.LANGUAGE: T_("Language"),
            me.SET_DOWNLOAD_DIRECTORY: T_("Set Download Directory"),
        }
        for entry, text in entries.items():
            self.entryconfigure(entry.value, label=text)
        self.language_menu.reload_text()


class ApplicationMenu(GuiElement):
    """Menu bar that is displayed at the top of the application."""

    def __init__(self, parent: Union[tk.Widget, tk.Tk]):
        super().__init__(parent)
        self.file_button = ttk.Menubutton(self, takefocus=False)
        self.file_menu = FileMenu(self.file_button)
        self.options_button = ttk.Menubutton(self, takefocus=False)
        self.options_menu = OptionMenu(self.options_button)
        self._initialize()

    def _initialize(self) -> None:
        self.file_button.grid(column=0, row=0)
        self.file_button.configure(menu=self.file_menu)
        self.options_button.grid(column=1, row=0)
        self.options_button.configure(menu=self.options_menu)
        self.reload_text()

    def reload_text(self) -> None:
        self.file_button.configure(text=T_("File"))
        self.options_button.configure(text=T_("Options"))
        self.file_menu.reload_text()
        self.options_menu.reload_text()


class ApplicationWindow:
    """The container for the main window.

    Parameters
    ----------
    update_function : Optional[Callable[[], None]], optional
        A function that will be called periodically, around 100 times
        per second. This should be a function that needs to execute
        constantly on the main thread. By default None.

    update_frequency: int, optional
        The amount of time that passes between each call to
        `update_function`, in milliseconds. By default 16.

    """

    def __init__(
        self,
        update_function: Optional[Callable[[], None]] = None,
        update_frequency: int = 16,
    ) -> None:
        self.root = tk.Tk()
        self.root.title("Download Manager")
        self.update_function = update_function
        self.update_frequency = update_frequency
        self._fix_treeview_tags()
        self.application_menu = ApplicationMenu(self.root)
        self.download_input_area = DownloadInputArea(self.root)
        self.download_list_area = DownloadListArea(self.root)
        self.stop = False
        self._initialize()

    def _initialize(self) -> None:
        self.root.minsize(960, 540)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)
        self.application_menu.grid(column=0, row=0, sticky="WE")
        self.download_input_area.grid(column=0, row=1, sticky="NSWE")
        self.download_list_area.grid(column=0, row=2, sticky="NSWE")
        # self._load_icon()

    def start(self) -> None:
        """Start the main window and the Tk mainloop."""
        if self.update_function is not None:
            self._periodic_refresh()
        self.root.mainloop()

    def _load_icon(self) -> None:
        """Load the icon for the main window."""
        path = importlib.resources.path("downloadmagic", "icon.ico")
        with path as file:
            self.root.iconbitmap(file)

    def _periodic_refresh(self) -> None:
        if self.stop:
            self.root.destroy()
        self.update_function()  # type: ignore
        self.root.after(self.update_frequency, self._periodic_refresh)

    def _fix_treeview_tags(self) -> None:
        """Fixes a bug with treeview in python >= 3.7.3

        See https://bugs.python.org/issue36468 for more info.
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
