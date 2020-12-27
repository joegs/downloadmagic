import asyncio
import json
import queue
import threading as th
from typing import Iterator, List, cast

import websockets

from messaging.base import Message, MessageBroker, Subscriber


class WebsocketBrokerServer(th.Thread):
    def __init__(self, host: str, port: int) -> None:
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.input_queue: queue.Queue[str] = queue.Queue()
        self.output_queue: queue.Queue[str] = queue.Queue()
        self.stop = th.Event()
        self.sent = th.Event()

    def input_messages(self) -> Iterator[str]:
        while True:
            try:
                message: str = self.input_queue.get_nowait()
                yield message
            except queue.Empty:
                break

    def output_messages(self) -> Iterator[str]:
        message_received = False
        while True:
            try:
                message: str = self.output_queue.get_nowait()
                message_received = True
                yield message
            except queue.Empty:
                break
        if message_received:
            self.sent.clear()

    async def consumer_handler(
        self, websocket: websockets.WebSocketServerProtocol, path: str
    ) -> None:
        async for message in websocket:
            m = cast(str, message)
            try:
                self.output_queue.put_nowait(m)
                self.sent.set()
            except queue.Full:
                pass

    async def producer_handler(
        self, websocket: websockets.WebSocketServerProtocol, path: str
    ) -> None:
        while True:
            for message in self.input_messages():
                await websocket.send(message)
            await asyncio.sleep(1 / 50)

    async def handler(
        self, websocket: websockets.WebSocketServerProtocol, path: str
    ) -> None:
        try:
            consumer_task = asyncio.create_task(self.consumer_handler(websocket, path))
            producer_task = asyncio.create_task(self.producer_handler(websocket, path))
            done, pending = await asyncio.wait(
                [consumer_task, producer_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
        finally:
            pass

    async def start_server(self) -> None:
        event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(event_loop)
        async with websockets.serve(self.handler, self.host, self.port) as server:
            while True:
                await asyncio.sleep(1 / 50)
                if self.stop.is_set():
                    break

    def run(self) -> None:
        asyncio.run(self.start_server())


class WebsocketBrokerClient(th.Thread):
    def __init__(self, uri: str) -> None:
        super().__init__(daemon=True)
        self.uri = uri
        self.input_queue: queue.Queue[str] = queue.Queue()
        self.output_queue: queue.Queue[str] = queue.Queue()
        self.stop = th.Event()
        self.sent = th.Event()

    def input_messages(self) -> Iterator[str]:
        while True:
            try:
                message: str = self.input_queue.get_nowait()
                yield message
            except queue.Empty:
                break

    def output_messages(self) -> Iterator[str]:
        message_received = False
        while True:
            try:
                message: str = self.output_queue.get_nowait()
                message_received = True
                yield message
            except queue.Empty:
                break
        if message_received:
            self.sent.clear()

    async def consumer_handler(
        self, websocket: websockets.WebSocketClientProtocol
    ) -> None:
        async for message in websocket:
            m = cast(str, message)
            try:
                self.output_queue.put_nowait(m)
                self.sent.set()
            except queue.Full:
                pass

    async def producer_handler(
        self, websocket: websockets.WebSocketClientProtocol
    ) -> None:
        while True:
            for message in self.input_messages():
                await websocket.send(message)
            await asyncio.sleep(1 / 50)
            if self.stop.is_set():
                return

    async def start_connection(self) -> None:
        try:
            async with websockets.connect(self.uri) as websocket:
                consumer_task = asyncio.create_task(self.consumer_handler(websocket))
                producer_task = asyncio.create_task(self.producer_handler(websocket))
                done, pending = await asyncio.wait(
                    [consumer_task, producer_task],
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    task.cancel()
        finally:
            pass

    def run(self) -> None:
        asyncio.run(self.start_connection())


class SocketServerMessageBroker(MessageBroker):
    def __init__(self, host: str, port: int) -> None:
        self.subscribers: List[Subscriber] = []
        self.server = WebsocketBrokerServer(host, port)
        self.server.start()
        thread = th.Thread(target=self._check_server_for_messages, daemon=True)
        thread.start()

    def _check_server_for_messages(self) -> None:
        while True:
            self.server.sent.wait()
            for m in self.server.output_messages():
                decoded_message = json.loads(m)
                message = cast(Message, decoded_message)
                self.send_message(message)

    def _send_message_to_websocket(self, message: Message) -> None:
        encoded_message = json.dumps(message)
        try:
            self.server.input_queue.put_nowait(encoded_message)
        except queue.Full:
            pass

    def send_message(self, message: Message) -> None:
        topic = message["topic"]
        if topic == "downloadclient":
            self._send_message_to_websocket(message)
        for subscriber in self.subscribers:
            if topic in subscriber.topics:
                subscriber.receive_message(message)

    def subscribe(self, subscriber: Subscriber) -> None:
        self.subscribers.append(subscriber)
        return super().subscribe(subscriber)

    def unsubscribe(self, subscriber: Subscriber) -> None:
        self.subscribers.remove(subscriber)


class SocketClientMessageBroker(MessageBroker):
    def __init__(self, uri: str) -> None:
        self.subscribers: List[Subscriber] = []
        self.client = WebsocketBrokerClient(uri)
        self.client.start()
        thread = th.Thread(target=self._check_server_for_messages, daemon=True)
        thread.start()

    def _check_server_for_messages(self) -> None:
        while True:
            self.client.sent.wait()
            for m in self.client.output_messages():
                decoded_message = json.loads(m)
                message = cast(Message, decoded_message)
                self.send_message(message)

    def _send_message_to_websocket(self, message: Message) -> None:
        encoded_message = json.dumps(message)
        try:
            self.client.input_queue.put_nowait(encoded_message)
        except queue.Full:
            pass

    def send_message(self, message: Message) -> None:
        topic = message["topic"]
        if topic == "downloadserver":
            self._send_message_to_websocket(message)
        for subscriber in self.subscribers:
            if topic in subscriber.topics:
                subscriber.receive_message(message)

    def subscribe(self, subscriber: Subscriber) -> None:
        self.subscribers.append(subscriber)
        return super().subscribe(subscriber)

    def unsubscribe(self, subscriber: Subscriber) -> None:
        self.subscribers.remove(subscriber)
