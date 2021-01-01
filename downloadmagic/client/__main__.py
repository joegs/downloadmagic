import sys

from downloadmagic.client import DownloadClient
from downloadmagic.online import SocketClientMessageBroker

if __name__ == "__main__":
    uri = sys.argv[1]
    client_broker = SocketClientMessageBroker(uri)
    client = DownloadClient(client_broker)
    client.start()
    client_broker.client.stop.set()
