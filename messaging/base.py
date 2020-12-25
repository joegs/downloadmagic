from abc import ABC, abstractmethod
from typing import Any, Dict, Set

Message = Dict[str, Any]


class Subscriber(ABC):
    def __init__(self, topics: Set[str]) -> None:
        self.topics = topics

    @abstractmethod
    def receive_message(self, message: Message) -> None:
        ...


class MessageBroker(ABC):
    @abstractmethod
    def send_message(self, message: Message) -> None:
        ...

    @abstractmethod
    def subscribe(self, subscriber: Subscriber) -> None:
        ...

    @abstractmethod
    def unsubscribe(self, subscriber: Subscriber) -> None:
        ...