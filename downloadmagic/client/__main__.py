import sys

from downloadmagic.client import Client
from downloadmagic.online import SocketClientMessageBroker

if __name__ == "__main__":
    uri = sys.argv[1]
    client_broker = SocketClientMessageBroker(uri)
    client = Client(client_broker)
    client.start()
    client_broker.client.stop.set()
