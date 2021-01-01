from messaging import DefaultMessageBroker

from downloadmagic.client import DownloadClient
from downloadmagic.server import DownloadServer

if __name__ == "__main__":
    broker = DefaultMessageBroker()
    server = DownloadServer(broker)
    server.start()
    client = DownloadClient(broker)
    client.start()
