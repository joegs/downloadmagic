from abc import ABC, abstractmethod
from typing import Set, TypedDict


class Message(TypedDict):
    """Schema definition for a basic message.

    This class is intended to serve as a schema for a basic message. It
    describes the attributes of the message and their data types.

    Messages hold data and serve as a way to transfer that data. A
    message is a normal dictionary that fulfills the schema described
    by this class.

    Custom messages may be defined by subclassing this class. This
    class may be used as a type hint on normal dictionaries that
    fulfill the schema, or as a callable to create a message.

    This is not a real class, for more information, see PEP 589:
    https://www.python.org/dev/peps/pep-0589/

    Attributes
    ----------
    topic : str
        The topic of the message.
    action : str
        The action of the message. It describes the purpose of the
        message.

    """

    topic: str
    action: str


class Subscriber(ABC):
    """An object that receives messages.

    This is an abstract class, and as such it can't be instantiated
    directly.

    Parameters
    ----------
    topics : Set[str]

    Attributes
    ----------
    topics : Set[str]
        The topics of the subscriber. These are intended to be used by
        other objects to decide whether or not the subscriber should
        receive a message.
    """

    def __init__(self, topics: Set[str]) -> None:
        self.topics: Set[str] = topics

    @abstractmethod
    def receive_message(self, message: Message) -> None:
        """Receive a message.

        The way the message is received is left to the implementation.

        Parameters
        ----------
        message: Message

        """
        ...


class MessageBroker(ABC):
    """An object that sends messages to subscribers.

    This is an abstract class, and as such it can't be instantiated
    directly.

    Subscribers that want to receive messages from this object must be
    registered with the `subscribe` method.

    """

    @abstractmethod
    def send_message(self, message: Message) -> None:
        """Send a message to the relevant subscribers.

        The way the message is sent and which subscribers receive it
        is left to the implementation.

        Parameters
        ----------
        message: Message

        """
        ...

    @abstractmethod
    def subscribe(self, subscriber: Subscriber) -> None:
        """Register a `Subscriber`.

        A registered subscriber may receive messages sent from this
        message broker.

        Parameters
        ----------
        subscriber : Subscriber
            The subscriber to register.
        """
        ...

    @abstractmethod
    def unsubscribe(self, subscriber: Subscriber) -> None:
        """Remove a `Subscriber`.

        Subscribers that are removed cannot receive messages from this
        message broker anymore.

        Parameters
        ----------
        subscriber : Subscriber
            The subscriber to remove.
        """
        ...
