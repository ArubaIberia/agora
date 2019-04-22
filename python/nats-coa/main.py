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

# Ejemplo de peticion que se puede recibir en el topic
Sample = {
  "host": "cppm-address",
  "user": "cppm-api-user",
  "pass": "cppm-api-key",
  "endpoint_mac": "endpoint MAC address",
  "nas_ip": "NAS IP address for CoA",
  "threat": True,
}

async def onReceive(http, data):
  """Cambia los atributos de threat severity y status del endpoint, y le envia un CoA al nas_ip"""

  # Fake config object. Solo soportamos client_credentials
  cfg = {
    "clearpass": {
      "grant_type": "client_credentials",
      "api_host": data["host"],
      "client_id": data["user"],
      "client_secret": data["pass"],
    },
  }
  nas_ip = data["nas_ip"]
  endpoint_mac = data["endpoint_mac"]
  threat = data["threat"]

  # Inicio una sesión con el clearpass que está en el fichero de configuración.
  # Para cambiar las credenciales: python -m aruba.clearpass
  with clearpass.session(cfg, verify=False) as session:

      # Modifico el nivel de amenaza del endpoint
      update = {
        "attributes": {
          "Threat Severity": "Critical",
          "Threat Status": "In Progress",
        },
      }
      if not threat:
        update = {
          "attributes": {
            "Threat Severity": "Low",
            "Threat Status": "Resolved",
          },
        }
      async with http.patch(session.api_url + "/endpoint/mac-address/{}".format(endpoint_mac), headers=session.headers(), json=update) as response:
        if response.status != 200:
            return "Error actualizando endpoint: ({}) {}".format(response.status, await response.text())

      # Encuentro la última sesión en el switch
      query = {
        "filter": json.dumps({
          "callingstationid": endpoint_mac,
        }),
        "sort": "-acctstarttime",
        "limit": 1,
      }
      session_id = ""
      async with http.get(session.api_url + "/session", headers=session.headers(), params=query) as response:
        if response.status != 200:
            return "Error localizando sesion: ({}) {}".format(response.status, await response.text())
        for item in (await response.json())["_embedded"]["items"]:
            if nas_ip in item["nasipaddress"]:
                session_id = item["id"]
                break

      # Fuerzo un reconnect de esa sesión
      confirm = { "confirm_disconnect": True }
      async with http.post(session.api_url+"/session/{}/disconnect".format(session_id), headers=session.headers(), json=confirm) as response:
        if response.status != 200:
            return "Error desconectando sesion: ({}) {}".format(response.status, await response.text())

      # return None si no hay error
      return None

async def message_handler(msg):
  """Gestiona mensajes recibidos"""
  try:
    subject, data = msg.subject, json.loads(msg.data.decode())
    for key in Sample:
      if not key in data:
        print("Recibido mensaje mal formado '{}': {}".format(subject, data))
        return
    print("Recibido mensaje bien formado: {}".format(data))
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=False)) as http:
      result = await onReceive(http, data)
    if result is None:
      print("Cambio completado")
    else:
      print("Error cambiando rol al sensor: {}".format(result))
  except:
    print("Excepcion promesando mensaje: {}".format(traceback.format_exc()))

async def process(loop, url, topic):
  """Process messages coming from the topic"""
  nc = NATS()
  await nc.connect(url, loop=loop)
  print("Conexión establecida a url {}".format(url))
  try:
    sid = await nc.subscribe(topic, cb=message_handler)
    print("Suscripción a topico {}: {}".format(topic, sid))
    try:
      while True:
        await asyncio.sleep(1000, loop=loop)
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
  args = parser.parse_args()
  if args.url == "" or args.topic == "":
    print("URL y topic no pueden estar vacios")
    sys.exit(-1)
  loop = asyncio.get_event_loop()
  loop.run_until_complete(process(loop, args.url, args.topic))
  loop.close()
