import sys
import time

from downloadmagic.server import DownloadServer
from downloadmagic.online import SocketServerMessageBroker

if __name__ == "__main__":
    host = sys.argv[1]
    port = int(sys.argv[2])
    server_broker = SocketServerMessageBroker(host, port)
    server = DownloadServer(server_broker)
    server.start()
    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            server_broker.server.stop.set()
            break
