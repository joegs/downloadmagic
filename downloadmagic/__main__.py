from messaging import DefaultMessageBroker

from downloadmagic.client import DownloadClient
from downloadmagic.server import DownloadServer
from downloadmagic.translation import TR

if __name__ == "__main__":
    TR.language = "en"
    broker = DefaultMessageBroker()
    server = DownloadServer(broker)
    server.start()
    client = DownloadClient(broker)
    client.start()
    server.stop_server()
