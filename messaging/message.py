import queue
import threading as th
from typing import Iterator, List, Set

from messaging.base import Message, MessageBroker, Subscriber


class ThreadSubscriber(Subscriber):
    """Thread safe subscriber.

    This subscriber uses a synchronized queue to receive messages, and
    as such, it's thread safe.

    Parameters
    ----------
    topics : Set[str]
        The topics of the subscriber.
    input_size : int, optional
        The maximum ammount of messages that the queue may hold, by
        default 10. Messages received when the queue is full will be
        ignored.

    Attributes
    ----------
    received : threading.Event
        An event that indicates if a message has been received. Other
        objects may wait on this event.
    input_queue : queue.Queue
        A thread safe synchronized queue used to store the messages
        received. Other objects may retrieve messages from this queue.

    """

    def __init__(self, topics: Set[str], input_size: int = 10) -> None:
        super().__init__(topics)
        self.received = th.Event()
        self.input_queue: queue.Queue[Message] = queue.Queue(input_size)

    def receive_message(self, message: Message) -> None:
        """Put a message on the `input_queue`.

        Messages received when the queue is full will be ignored.

        Parameters
        ----------
        message: Message

        """
        try:
            self.input_queue.put_nowait(message)
        except queue.Full:
            return
        self.received.set()

    def messages(self) -> Iterator[Message]:
        """Return an iterator of the messages received.

        This method is a generator that retrieves and returns the
        messages stored in the `input_queue`.

        Once all messages have been retrieved, the `received` event
        is cleared.

        Yields
        ------
        message: Message
            A message stored in the `input_queue`.

        """
        message_received = False
        while True:
            try:
                message: Message = self.input_queue.get_nowait()
                message_received = True
                yield message
            except queue.Empty:
                break
        if message_received:
            self.received.clear()


class DefaultMessageBroker(MessageBroker):
    """Default implementation of :class:`MessageBroker`.

    Subscribers are stored on a list, and messages are sent to
    subscribers that contain the topic of the message in their own
    topics.

    Attributes
    ----------
    subscribers : List[Subscriber]
        A list of the subscribers registered to this message broker.

    """

    def __init__(self) -> None:
        super().__init__()
        self.subscribers: List[Subscriber] = []

    def send_message(self, message: Message) -> None:
        """Send a message to the relevant subscribers.

        Only subscribers that contain the topic of the message on their
        own topics will receive the message.

        Parameters
        ----------
        message : Message

        """
        topic: str = message["topic"]
        for subscriber in self.subscribers:
            if topic in subscriber.topics:
                subscriber.receive_message(message)

    def subscribe(self, subscriber: Subscriber) -> None:
        self.subscribers.append(subscriber)

    def unsubscribe(self, subscriber: Subscriber) -> None:
        self.subscribers.remove(subscriber)
