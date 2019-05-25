#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import traceback
import asyncio
import aiohttp

from nats.aio.client import Client as NATS

class Suscription(object):

    """NATS Server suscription.

    Asynchronous suscription to a NATS server.
    See https://nats.io/documentation/
    """

    def __init__(self, natsURL, topic, verifySSL=False):
        """Suscribe to the given topic of the NATS server at natsURL"""
        self.natsURL = natsURL
        self.topic = topic
        self.verifySSL = verifySSL

    async def _sink(self, loop, asyncQueue, asyncCallback):
        natsConn = NATS()
        await natsConn.connect(self.natsURL, loop=loop)
        logging.debug("Suscription - Connected to NATS server")
        try:
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=self.verifySSL)) as httpSession:
                async def handler(msg):
                    logging.debug("Suscription - Received message")
                    await self._task(natsConn, msg, httpSession, asyncCallback)
                sid = await natsConn.subscribe(self.topic, "workers", cb=handler)
                logging.debug("Suscription - subscribed to topic {}".format(self.topic))
                try:
                    # Wait until something is pushed to the queue (cancellation signal)
                    await asyncQueue.get()
                    logging.debug("Suscription - Finished suscription to {}".format(self.topic))
                finally:
                    await natsConn.unsubscribe(sid)
        finally:
            logging.debug("Suscription - Disconnecting from NATS server")
            await natsConn.close()

    # Asynchronous task to be run pn message arrival
    async def _task(self, natsConn, natsMsg, httpSession, asyncCallback):
        reply = ""
        try:
            logging.debug("Suscription::task - Received message")
            reply = await asyncCallback(httpSession, natsMsg.data)
        except:
            reply = traceback.format_exc()
            logging.error("Suscription::task - error {}".format(reply))
        if natsMsg.reply:
            if hasattr(reply, 'encode'):
                reply = reply.encode('utf-8')
            await natsConn.publish(natsMsg.reply, reply)

    def go(self, loop, asyncCallback):
        """Process all messages in the topic.
        Each message triggers a call to the asyncCallback func, asyncCallback(aiohttpClient, bytes)
        This functions returns a cancellation closure, e.g.
        >>> cancel = new Suscription(url, topic, False)(loop, callback)
        >>> # ... do your stuff while messages are received
        >>> await cancel()
        """
        queue = asyncio.Queue(1, loop=loop)
        loop.create_task(self._sink(loop, queue, asyncCallback))
        async def cancel():
            await queue.put(False)
        return cancel
