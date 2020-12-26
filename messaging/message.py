import queue
import threading as th
from typing import Iterator, List, Set

from messaging.base import Message, MessageBroker, Subscriber


class ThreadSubscriber(Subscriber):
    def __init__(self, topics: Set[str], input_size: int = 10):
        super().__init__(topics)
        self.received = th.Event()
        self.input_queue: queue.Queue[Message] = queue.Queue(input_size)

    def receive_message(self, message: Message) -> None:
        try:
            self.input_queue.put_nowait(message)
        except queue.Full:
            return
        self.received.set()

    def messages(self) -> Iterator[Message]:
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
    def __init__(self) -> None:
        super().__init__()
        self.subscribers: List[Subscriber] = []

    def send_message(self, message: Message) -> None:
        topic = message["topic"]
        for subscriber in self.subscribers:
            if topic in subscriber.topics:
                subscriber.receive_message(message)

    def subscribe(self, subscriber: Subscriber) -> None:
        self.subscribers.append(subscriber)
        return super().subscribe(subscriber)

    def unsubscribe(self, subscriber: Subscriber) -> None:
        self.subscribers.remove(subscriber)
