from messaging import DefaultMessageBroker

from downloadmagic.client import DownloadClient
from downloadmagic.config import ConfigOption, Configuration
from downloadmagic.server import DownloadServer
from downloadmagic.translation import TR

if __name__ == "__main__":
    configuration = Configuration()
    configuration.load_config()
    language = configuration.get_config_value(ConfigOption.LANGUAGE)
    TR.language = language
    broker = DefaultMessageBroker()
    server = DownloadServer(broker)
    server.start()
    client = DownloadClient(broker, configuration)
    client.start()
    server.stop_server()
