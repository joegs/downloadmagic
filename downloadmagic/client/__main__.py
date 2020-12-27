import time

from downloadmagic.client import Client
from messaging.online import SocketClientMessageBroker

if __name__ == "__main__":
    client_broker = SocketClientMessageBroker("ws://192.168.0.19:8765")
    client = Client(client_broker)
    client.start()
    client_broker.client.stop.set()
