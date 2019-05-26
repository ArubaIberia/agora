#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import traceback
import asyncio
import aiohttp

from contextlib import asynccontextmanager, AsyncExitStack
from nats.aio.client import Client as NATS


class Suscription(object):

    """NATS Server suscription.

    Asynchronous suscription to a NATS server.
    See https://nats.io/documentation/
    """

    def __init__(self, natsConn, loop):
        """Manage suscriptions to topics in the provided connection"""
        self.natsConn = natsConn
        self.loop = loop

    async def _sink(self, topic, cancelQueue, asyncCallback):
        async def handler(msg):
            logging.debug("Suscription - Received message on {}".format(topic))
            await self._onMessage(self.natsConn, topic, msg, asyncCallback)
        sid = await self.natsConn.subscribe(topic, "workers", cb=handler)
        try:
            logging.debug("Suscription - subscribed to {}".format(topic))
            # Wait until something is pushed to the queue (cancellation signal)
            await cancelQueue.get()
            logging.debug("Suscription - Finished suscription to {}".format(topic))
            await cancelQueue.task_done()
        finally:
            await self.natsConn.unsubscribe(sid)

    # Asynchronous task to be run on message arrival
    async def _onMessage(self, natsConn, topic, natsMsg, asyncCallback):
        reply = ""
        try:
            logging.debug("Suscription::task - Received message on {}".format(topic))
            reply = await asyncCallback(topic, natsMsg.data)
        except:
            reply = traceback.format_exc()
            logging.error("Suscription::task - error on {}: {}".format(topic, reply))
        if natsMsg.reply:
            if hasattr(reply, 'encode'):
                reply = reply.encode('utf-8')
            await natsConn.publish(natsMsg.reply, reply)

    @asynccontextmanager
    async def topic(self, topic, asyncCallback):
        """Process all messages in the topic.
        Each message triggers a call to the asyncCallback func, asyncCallback(topic, msgBytes)
        This functions returns a cancellation closure, e.g.
        >>> cancel = new Suscription(url, topic, False)(loop, callback)
        >>> # ... do your stuff while messages are received
        >>> await cancel()
        """
        queue = asyncio.Queue(1, loop=self.loop)
        self.loop.create_task(self._sink(topic, queue, asyncCallback))
        yield None
        await queue.put(False)

    @asynccontextmanager
    async def refresh(self, syncRefreshFunc, timeout):
        """Keeps calling the refresh function in the background, every 'timeout' seconds"""
        queue = asyncio.Queue(1, loop=self.loop)
        async def asyncRefresh():
            while True:
                try:
                    await asyncio.wait_for(queue.get(), timeout=timeout, loop=self.loop)
                except TimeoutError:
                    syncRefreshFunc()
        self.loop.create_task(asyncRefresh())
        yield None
        await queue.put(False)


@asynccontextmanager
async def suscription(natsURL, loop):
    natsConn = NATS()
    await natsConn.connect(natsURL, loop=loop)
    logging.debug("Suscription - Connected to NATS server")
    yield Suscription(natsConn, loop)
    natsConn.close()


class App():

    """Message-based Application.

    Manages a Session and a NATS connection, to subscribe to
    NATS topics and trigger actions on the session.
    """

    def __init__(self, natsURL, contextCallback, verify=True):
        """Build an app connected to the given NATS server.
        
        contextCallback must be a function that takes no arguments and returns a
        contextmanager, e.g:

        Works:
        >>> app = App(myURL, lambda: clearpass.session(config))

        Does not work:
        >>> app = App(myURL, clearpass.session(config))
        """
        self._loop = asyncio.get_event_loop()
        self._natsURL = natsURL
        self._context = contextCallback
        self._verify = verify
        self._stop = None
        self._topics = dict()
        self.prodSession = None
        self.httpSession = None
        self.natsSession = None

    async def start(self):
        "Start the app. This is not reentrant, an only be started once."
        logging.debug("Iniciando proceso principal")
        async with AsyncExitStack() as stack:
            prodSession = stack.enter_context(self._context())
            logging.debug("Iniciado contexto de aplicación")
            httpSession = await stack.enter_async_context(aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=self._verify)))
            logging.debug("Iniciado pool HTTP")
            natsSession = await stack.enter_async_context(suscription(self._natsURL, self._loop))
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

    async def subscribe(self, topic, asyncCallback):
        """Subscribe a topic. asyncCallback will be called with topic name, and message.

        Caution: asyncCallback must be an asyncfunction, not a lambda. E.g. this doesn't work:

        >>> app.subscribe("topic", (lambda topic, msg: doStuff()))

        Instead you mst create an async callback function:

        >>> async def myCallback(topic, msg):
        >>>     return await doStuff()
        >>> app.subscribe("topic", myCallback)
        """
        async with AsyncExitStack() as stack:
            await stack.enter_async_context(self.natsSession.topic(topic, asyncCallback))
            logging.debug("Suscrito a tópico {}, esperando mensajes...".format(topic))
            self._topics[topic] = stack.pop_all().aclose

    async def stop(self):
        "Stop the nat connection and all subscritions. Call with await"
        for closeFunc in self._topics.values():
            await closeFunc()
        self._topics = dict()
        if self._stop is not None:
            await self._stop()
        self._stop = None

    async def unsubscribe(self, topic):
        "Unsubscribe from the topic. Call with await"
        closeFunc = self._topics.get(topic, None)
        if closeFunc is not None:
            await closeFunc()
            del self._topics[topic]
