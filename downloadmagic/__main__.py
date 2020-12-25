from messaging import DefaultMessageBroker

from downloadmagic.client import Client
from downloadmagic.server import DownloadServer

if __name__ == "__main__":
    broker = DefaultMessageBroker()
    server = DownloadServer(broker)
    server.start()
    client = Client(broker)
    client.start()
