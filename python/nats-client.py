#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# nats-client.py: Subscribe to a nats topic and wait for CoA requests
 
import sys
import requests
import json
import argparse
import asyncio
import traceback

from contextlib import contextmanager
from nats.aio.client import Client as NATS
from nats.aio.errors import ErrConnectionClosed, ErrTimeout, ErrNoServers
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

def switchRole(config, nas_ip, endpoint_mac, threat):
  """Cambia los atributos de threat severity y status del endpoint, y le envia un CoA al nas_ip"""
  # Inicio una sesión con el clearpass que está en el fichero de configuración.
  # Para cambiar las credenciales: python -m aruba.clearpass
  with clearpass.session(config, verify=False) as session:

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
      response = requests.patch(session.api_url + "/endpoint/mac-address/{}".format(endpoint_mac), verify=False, headers=session.headers(), json=update)
      if response.status_code != 200:
          return "Error actualizando endpoint: ({}) {}".format(response.status_code, response.text)

      # Encuentro la última sesión en el switch
      query = {
        "filter": json.dumps({
          "nasipaddress": nas_ip,
          "callingstationid": endpoint_mac,
        }),
        "sort": "-acctstarttime",
        "limit": 1,
      }
      response = requests.get(session.api_url + "/session", verify=False, headers=session.headers(), params=query)
      if response.status_code != 200:
          return "Error localizando sesion: ({}) {}".format(response.status_code, response.text)
      session_id = response.json()["_embedded"]["items"][0]["id"]

      # Fuerzo un reconnect de esa sesión
      confirm = { "confirm_disconnect": True }
      response = requests.post(session.api_url+"/session/{}/disconnect".format(session_id), verify=False, headers=session.headers(), json=confirm)
      if response.status_code != 200:
          return "Error desconectando sesion: ({}) {}".format(response.status_code, response.text)

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
    # Fake comnfig object. Solo soportamos client_credentials
    cfg = {
      "clearpass": {
        "grant_type": "client_credentials",
        "api_host": data["host"],
        "client_id": data["user"],
        "client_secret": data["pass"],
      },
    }
    print("Recibido mensaje bien formado: {}".format(data))
    result = switchRole(cfg, data["nas_ip"], data["endpoint_mac"], data["threat"])
    if result is None:
      print("Cambio completado")
    else:
      print("Error cambiando rol al sensor: {}".format(result))
  except:
    print("Excepcion promesando mensaje: {}".format(traceback.format_exc()))

async def process(loop, url, topic):
  """Process messages coming from the topic"""
  #def signal_handler(sig, frame):
  #  pass
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
    print("errando conexion a URL {}".format(url))
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