import time

from downloadmagic.server import DownloadServer
from messaging.online import SocketServerMessageBroker

if __name__ == "__main__":
    server_broker = SocketServerMessageBroker("192.168.0.19", 8765)
    server = DownloadServer(server_broker)
    server.start()
    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            server_broker.server.stop.set()
            break
