from downloadmagic.client.gui import ApplicationWindow
from messaging import ThreadSubscriber, MessageBroker, Message


class Client:
    def __init__(self, message_broker: MessageBroker) -> None:
        self.application_window = ApplicationWindow(self._process_messages)
        self.subscriber = ThreadSubscriber({"downloadclient"})
        self.message_broker = message_broker
        self.message_broker.subscribe(self.subscriber)

    def _process_message(self, message: Message) -> None:
        pass

    def _process_messages(self) -> None:
        for message in self.subscriber.messages():
            self._process_message(message)

    def start(self) -> None:
        self.application_window.start()
