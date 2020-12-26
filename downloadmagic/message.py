from messaging import Message


class DownloadInfoMessage(Message):
    download_id: int
    url: str
    download_directory: str
    size: int
    filename: str
    filepath: str
    is_pausable: bool


class DownloadOperationMessage(Message):
    download_id: int
    download_operation: str


class DownloadStatusMessage(Message):
    download_id: int
    status: str
    downloaded_bytes: int
    progress: float
    speed: float


class CreateDownloadMessage(Message):
    url: str
    download_directory: str
