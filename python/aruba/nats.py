#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import traceback
import asyncio
import aiohttp

from concurrent.futures import TimeoutError
from contextlib import AsyncExitStack
from typing import Dict, Callable, Optional, Awaitable, ContextManager, AsyncContextManager
from nats.aio.client import Client as NATS, Msg # type: ignore
from aruba.common import Session

AsyncCallback = Callable[[str, bytes], Awaitable[Optional[bytes]]]


class Suscription(object):

    """NATS Server suscription.

    Asynchronous suscription to a NATS server.
    See https://nats.io/documentation/
    """

    def __init__(self, natsConn: NATS, loop: asyncio.AbstractEventLoop) -> None:
        """Manage suscriptions to topics in the provided connection"""
        self.natsConn = natsConn
        self.loop = loop

    async def _sink(self, topic: str, cancelQueue: asyncio.Queue, asyncCallback: AsyncCallback) -> None:
        async def handler(msg: bytes):
            logging.debug("Suscription - Received message on {}".format(topic))
            await self._onMessage(self.natsConn, topic, msg, asyncCallback)
        sid = await self.natsConn.subscribe(topic, "workers", cb=handler)
        try:
            logging.debug("Suscription - subscribed to {}".format(topic))
            # Wait until something is pushed to the queue (cancellation signal)
            await cancelQueue.get()
            logging.debug("Suscription - Finished suscription to {}".format(topic))
            cancelQueue.task_done()
        finally:
            await self.natsConn.unsubscribe(sid)

    # Asynchronous task to be run on message arrival
    async def _onMessage(self, natsConn: NATS, topic: str, natsMsg: Msg, asyncCallback: AsyncCallback) -> None:
        reply: Optional[bytes] = None
        try:
            logging.debug("Suscription::task - Received message on {}".format(topic))
            reply = await asyncCallback(topic, natsMsg.data)
        except:
            reply = traceback.format_exc().encode('utf-8')
            logging.error("Suscription::task - error on {}: {}".format(topic, reply))
        if natsMsg.reply:
            if reply is None:
                reply = "".encode('utf-8')
            await natsConn.publish(natsMsg.reply, reply)

    def topic(self, topic: str, asyncCallback: AsyncCallback) -> AsyncContextManager[None]:
        """Process all messages in the topic.
        Each message triggers a call to the asyncCallback func, asyncCallback(topic, msgBytes)
        This functions returns a cancellation closure, e.g.
        >>> cancel = new Suscription(url, topic, False)(loop, callback)
        >>> # ... do your stuff while messages are received
        >>> await cancel()
        """
        queue: asyncio.Queue = asyncio.Queue(1, loop=self.loop)
        suscr = self
        class _topic(AsyncContextManager[None]):
            async def __aenter__(self) -> None:
                suscr.loop.create_task(suscr._sink(topic, queue, asyncCallback))
            async def __aexit__(self, exc_type, exc, tb) -> None:
                await queue.put(False)
        return _topic()

    def refresh(self, syncRefreshFunc: Callable[[], None], timeout: float) -> AsyncContextManager[None]:
        """Keeps calling the refresh function in the background, every 'timeout' seconds"""
        queue: asyncio.Queue = asyncio.Queue(1, loop=self.loop)
        suscr = self
        class _refresh(AsyncContextManager[None]):
            async def refresh(self) -> None:
                while True:
                    try:
                        await asyncio.wait_for(queue.get(), timeout=timeout, loop=suscr.loop)
                    except TimeoutError:
                        syncRefreshFunc()
            async def __aenter__(self) -> None:
                suscr.loop.create_task(self.refresh())
            async def __aexit__(self, exc_type, exc, tb) -> None:
                await queue.put(False)
        return _refresh()


class suscription(AsyncContextManager[Suscription]):

    def __init__(self, natsURL: str, loop: asyncio.AbstractEventLoop) -> None:
        self.natsURL = natsURL
        self.loop = loop
        self.natsConn = NATS()

    async def __aenter__(self) -> Suscription:
        await self.natsConn.connect(self.natsURL, loop=self.loop)
        logging.debug("Suscription - Connected to NATS server")
        return Suscription(self.natsConn, self.loop)

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.natsConn.close()


class App(object):

    """Message-based Application.

    Manages a Session and a NATS connection, to subscribe to
    NATS topics and trigger actions on the session.
    """

    def __init__(self, natsURL: str, contextCallback: Callable[[], ContextManager],
        verify: bool = True, loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        """Build an app connected to the given NATS server.

        contextCallback must be a function that takes no arguments and returns a
        contextmanager, e.g:

        Works:
        >>> app = App(myURL, lambda: clearpass.session(config))

        Does not work:
        >>> app = App(myURL, clearpass.session(config))
        """
        self._natsURL = natsURL
        self._context = contextCallback
        self._verify = verify
        self._stop: Optional[Callable[[], Awaitable[None]]] = None
        self._topics: Dict[str, Callable[[], Awaitable]] = dict()
        self.loop = loop if loop is not None else asyncio.get_event_loop()
        self.prodSession: Optional[Session] = None
        self.httpSession: Optional[aiohttp.ClientSession] = None
        self.natsSession: Optional[Suscription] = None

    async def start(self) -> None:
        "Start the app. This is not reentrant, can only be started once."
        logging.debug("Iniciando proceso principal")
        async with AsyncExitStack() as stack:
            prodSession = stack.enter_context(self._context())
            logging.debug("Iniciado contexto de aplicación")
            httpSession = await stack.enter_async_context(aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=self._verify)))
            logging.debug("Iniciado pool HTTP")
            natsSession = await stack.enter_async_context(suscription(self._natsURL, self.loop))
            logging.debug("Lanzada conexion a NATS URL")
            self.prodSession = prodSession
            self.httpSession = httpSession
            self.natsSession = natsSession
            # If session supports refresh, refresh it.
            if hasattr(prodSession, "refresh"):
                await stack.enter_async_context(natsSession.refresh(prodSession.refresh, 7200))
                logging.debug("Lanzado proceso de refresco de sesion")
            self._stop = stack.pop_all().aclose
            self._topics = dict()

    async def subscribe(self, topic: str, asyncCallback: AsyncCallback) -> None:
        """Subscribe a topic. asyncCallback will be called with topic name, and message.

        Caution: asyncCallback must be an asyncfunction, not a lambda. E.g. this doesn't work:

        >>> app.subscribe("topic", (lambda topic, msg: doStuff()))

        Instead you mst create an async callback function:

        >>> async def myCallback(topic, msg):
        >>>     return await doStuff()
        >>> app.subscribe("topic", myCallback)
        """
        if self.natsSession is None:
            raise ValueError("Must start before subscribe")
        async with AsyncExitStack() as stack:
            await stack.enter_async_context(self.natsSession.topic(topic, asyncCallback))
            logging.debug("Suscrito a tópico {}, esperando mensajes...".format(topic))
            self._topics[topic] = stack.pop_all().aclose

    async def stop(self) -> None:
        "Stop the nat connection and all subscritions. Call with await"
        for closeFunc in self._topics.values():
            await closeFunc()
        self._topics = dict()
        if self._stop is not None:
            await self._stop()
        self._stop = None

    async def unsubscribe(self, topic: str) -> None:
        "Unsubscribe from the topic. Call with await"
        closeFunc = self._topics.get(topic, None)
        if closeFunc is not None:
            await closeFunc()
            del self._topics[topic]

    def forever(self) -> None:
        self.loop.run_forever()
