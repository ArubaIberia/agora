#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import traceback
import asyncio
import aiohttp

from nats.aio.client import Client as NATS
from contextlib import asynccontextmanager


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
