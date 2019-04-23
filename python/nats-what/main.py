#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# nats-client.py: Subscribe to a nats topic and wait for CoA requests
# Requisitos:
#
# pip3 install aiohttp
# pip3 install cchardet
# pip3 install aiodns
# pip3 install asyncio-nats-client

import sys
import json
import argparse
import asyncio
import traceback
import aiohttp

from nats.aio.client import Client as NATS

from aruba import Config, clearpass

# Desactivo el log de certificado autofirmado.
import logging
logging.captureWarnings(True)

async def onReceive(cppm, http, data):
  """Cambia los atributos de threat severity y status del endpoint, y le envia un CoA al nas_ip"""

  # Encuentro las últimas sesiones en APs instant
  query = {
    "sort": "-acctstarttime",
    "limit": 25,
  }
  endpoint_futures = list()
  sessions = list()
  async with http.get(cppm.api_url + "/session", headers=cppm.headers(), params=query) as response:
    if response.status != 200:
      return "Error localizando sesion: ({}) {}".format(response.status, await response.text())
    for item in (await response.json())["_embedded"]["items"]:
      if item["acctstoptime"] is None and item["nasipaddress"].startswith("1.1.1."):
        sessions.append(item)
        endpoint_futures.append(http.get(cppm.api_url + "/insight/endpoint/mac/{}".format(item["mac_address"]), headers=cppm.headers()))
      
    endpoints = list()
    for response in (await asyncio.gather(*endpoint_futures)):
      endpoints.append(await response.json())
  
    counter = 0
    message = ""
    sep = ""
    macs = dict()
    for session, endpoint in zip(sessions, endpoints):
      mac = session.get("mac_address", "")
      if mac in macs:
        continue
      macs[mac] = True
      nasport = session.get("nasportid", None)
      ssid = session.get("ssid", None)
      if ssid.startswith("__wired"):
        ssid = None
      category = endpoint.get("device_category", None)
      family = endpoint.get("device_family", None)
      if "amera" in category:
        family = "cámara i pe"
      ip = endpoint.get("ip", None)
      message += sep + "Dispositivo tipo " + family + ", en " + (("puerto numero " + nasport) if ssid is None else "ssid " + ssid) + ", con dirección i pe " + ip
      sep = ". "
    
    return message

async def message_handler(cfg, http, nc, msg):
    """Gestiona mensajes recibidos"""
    result = "Se ha producido un error"
    try:
      data = json.loads(msg.data.decode())
      print("Recibido mensaje bien formado: {}".format(data))
      result = await onReceive(cfg, http, data)
      if result is None:
        result = "orden procesada"
    except:
      print("Excepcion promesando mensaje: {}".format(traceback.format_exc()))
    if msg.reply:
      reply = json.dumps({ "fulfillmentText": result, "payload": { "google": { "expectUserResponse": False } } })
      await nc.publish(msg.reply, reply.encode('utf-8'))

async def process(loop, cfg, url, topic):
  """Process messages coming from the topic"""
  nc = NATS()
  await nc.connect(url, loop=loop)
  print("Conexión establecida a url {}".format(url))
  try:
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=False)) as http:
      cppm = clearpass.new_session(cfg, verify=False)
      @asyncio.coroutine
      def handler(msg):
        return message_handler(cppm, http, nc, msg)
      sid = await nc.subscribe(topic, "workers", cb=handler)
      print("Suscripción a topico {}: {}".format(topic, sid))
      try:
        while True:
          await asyncio.sleep(7200, loop=loop)
          # Refresh token
          cppm = clearpass.new_session(cfg, verify=False)
      finally:
        print("Eliminando suscripcion a topico {}".format(topic))
        await nc.unsubscribe(sid)
  finally:
    print("Cerrando conexion a URL {}".format(url))
    await nc.close()

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("url", help="URL del servidor gnatsd al que conectar")
  parser.add_argument("topic", help="Nombre del topic al que suscribirse")
  parser.add_argument("cppm", help="Dirección IP del servidor ClearPass")
  parser.add_argument("user", help="Nombre del usuario api")
  parser.add_argument("secret", help="Client_secret del usuario api")
  args = parser.parse_args()
  if args.url == "" or args.topic == "" or args.cppm == "" or args.user == "" or args.secret == "":
    print("Ninguno de los parametros pueden estar vacios")
    sys.exit(-1)
  # Fake config object. Solo soportamos client_credentials
  cfg = {
    "clearpass": {
      "grant_type": "client_credentials",
      "api_host": args.cppm,
      "client_id": args.user,
      "client_secret": args.secret,
    },
  }
  loop = asyncio.get_event_loop()
  loop.run_until_complete(process(loop, cfg, args.url, args.topic))
  loop.close()

