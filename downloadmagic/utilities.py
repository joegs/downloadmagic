import time


def convert_time(seconds: int) -> str:
    """Convert an amount of seconds into a human readable string.

    Parameters
    ----------
    seconds : int
        The number of seconds.

    Returns
    -------
    str
        A human readable time string in the format "DD HH:MM:SS"
    """
    intervals = [
        ("d", 86400),
        ("h", 3600),
        ("m", 60),
        ("s", 1),
    ]
    components = []
    for unit_name, interval_seconds in intervals:
        amount = seconds // interval_seconds
        seconds = seconds % interval_seconds
        components.append(f"{amount:>02}{unit_name}")
    result = f"{components[0]} "
    result += ":".join(components[1:])
    return result


def convert_size(size: float, decimal_places: int = 2) -> str:
    """Convert a size in bytes into a human readable string.

    Parameters
    ----------
    size : float
        The size to convert, in bytes.
    decimal_places : int, optional
        The decimal places to include in the output, by default 2.

    Returns
    -------
    str
        The same size, represented in the appropiate units.
    """
    for unit in ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]:
        if size < 1024.0 or unit == "PiB":
            break
        size /= 1024.0
    return f"{size:.{decimal_places}f} {unit}"


def calculate_remaining_time(speed: float, remaining_bytes: float) -> str:
    """Return a download remaining time, as a readable string.

    Parameters
    ----------
    speed : float
        The download speed, in bytes per second.
    remaining_bytes : float
        The remaining bytes of the download.

    Returns
    -------
    str
        The remaining time of the download, as a human readable string.
        If the speed is <= 0, this value is an empty string.
    """
    remaining_time = ""
    if speed > 0:
        seconds = int(remaining_bytes / speed)
        remaining_time = convert_time(seconds)
    return remaining_time


class Timer:
    """A simple timer.

    To use `Timer`, call `start()` to mark the starting time, and then
    call `measure()`, to save the `elapsed_time`.

    Subsequent measures will measure time from the start. To reset the
    timer and set a new start time, call `start()` again.

    Attributes
    ----------
    elapsed_time : float
        The time that transcurred from the moment the timer was
        started, to the moment it was measured.
    """

    def __init__(self) -> None:
        self._start_time: float = 0
        self._end_time: float = 0
        self.elapsed_time: float = 0

    def start(self) -> None:
        """Set the start time of the timer."""
        self._start_time = time.time()

    def measure(self) -> None:
        """Measure the time transcurred from the start of the timer."""
        self._end_time = time.time()
        self.elapsed_time = self._end_time - self._start_time
