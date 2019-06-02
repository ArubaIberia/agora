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
import time
import logging

from typing import Sequence, Tuple, Any, Dict, cast
from aruba import clearpass, nats, common


# Obtiene la lista de sesiones vivas
async def getSessions(cppmSession: common.Session, httpSession: aiohttp.ClientSession, nas_ips: Sequence[str]) -> Tuple[Any]:
    cppmURL = cppmSession.api_url + "/session"
    query = {
        "sort": "-acctstarttime",
        "limit": 25,
    }
    result: Dict[str, Any] = dict()
    async with httpSession.get(cppmURL, headers=cppmSession.headers(), params=cppmSession.params(query)) as response:
        if response.status != 200:
            raise ValueError("Error localizando sesion: ({}) {}".format(response.status, await response.text()))
        logging.debug("getSessions - sesiones obtenidas: {}".format(await response.text()))
        items = (await response.json())["_embedded"]["items"]
        # Me quedo con la sesion mas reciente de cada MAC
        now = time.time()
        for item in items:
            mac = item.get("mac_address", "")
            ini = int(item.get("acctstarttime", "0"))
            end = item.get("acctstoptime", None)
            nas = item.get("nasipaddress", "")
            if (end is None) and (now - ini < 28800) and (mac not in result) and coincide_nas(nas, nas_ips):
                result[mac] = item
    return cast(Tuple[Any], tuple(result.values()))

# Comprueba si el NAS coincide con alguno de los prefijos dados
def coincide_nas(nas_ip: str, prefijos: Sequence[str]) -> bool:
    return (prefijos is None) or any(nas_ip.startswith(p) for p in prefijos)

# Endpoints
async def getEndpoints(cppmSession: common.Session, httpSession: aiohttp.ClientSession, macs: Sequence[str]) -> Tuple[Any]:
    logging.debug("getEndpoints - Resolviendo endpoints para macs {}".format(macs))

    # Funcion auxiliar para convertir una lista de promesas, en un array de valores.
    async def gather(iterable):
        return await asyncio.gather(*tuple(iterable))

    endpoints = await gather(
        httpSession.get(cppmSession.api_url + "/insight/endpoint/mac/{}".format(mac),
            headers=cppmSession.headers(),
            params=cppmSession.params())
        for mac in macs)

    for text in await gather(ep.text() for ep in endpoints):
        logging.debug("getEndpoints - información de endpoint: {}".format(text))

    return await gather(ep.json() for ep in endpoints)

# Combina información de sesión y endpoint
def mergeData(sesiones: Sequence[Any], endpoints: Sequence[Any]) -> str:
    mensaje, sep = "", ""
    for session, endpoint in zip(sesiones, endpoints):
        nasport = session.get("nasportid", None)
        ssid = session.get("ssid", None)
        # La controladora usa SSIDs "__wired_xxx" cuando la conexión es cableada
        if (ssid is not None) and (ssid.startswith("__wired")):
            ssid = None
        category = endpoint.get("device_category", None)
        family = endpoint.get("device_family", None)
        if "amera" in category:
            family = "cámara i pe"
        ip = endpoint.get("ip", None)
        mensaje += (sep + "Dispositivo tipo " + family + ", en "
            + (("puerto numero " + nasport) if ssid is None else "ssid " + ssid)
            + ", con dirección i pe " + ip)
        sep = ". "

    if mensaje == "":
        mensaje = "ningún dispositivo conectado"
    return mensaje

# Gestiona las peticiones de Google
def googleEnumerate(app: nats.App, nas_ips: Sequence[str]) -> nats.AsyncCallback:
  async def handler(topic: str, msg: bytes) -> bytes:
    mensaje = ""
    try:
      # No se usa, pero ahí está...
      logging.debug("Recibida peticion: {}".format(json.loads(msg.decode('utf-8'))))
      # Obtenemos la información
      if app.prodSession is None or app.httpSession is None:
        raise ValueError("CPPM and HTTP Sessions must not be None")
      sesiones = await getSessions(app.prodSession, app.httpSession, nas_ips)
      macs = tuple(s["mac_address"] for s in sesiones)
      endpoints = await getEndpoints(app.prodSession, app.httpSession, macs)
      # Y generamos el mensaje
      mensaje = mergeData(sesiones, endpoints)
      logging.debug(f"Mensaje generado: {mensaje}")
    except:
      logging.error(traceback.format_exc())
      mensaje = "Se ha producido un error"
    return json.dumps({
      "fulfillmentText": mensaje,
      "payload": { "google": { "expectUserResponse": False } },
    }).encode('utf-8')
  return handler


if __name__ == "__main__":

  #fileHandler = RotatingFileHandler("nats-what.log", maxBytes=512*1024, backupCount=5)
  fileHandler = logging.StreamHandler(sys.stdout)
  logging.captureWarnings(True)
  logging.basicConfig(level=logging.DEBUG, handlers=(fileHandler,))

  parser = argparse.ArgumentParser()
  parser.add_argument("url", help="URL del servidor gnatsd al que conectar")
  parser.add_argument("topic", help="Nombre del topic al que suscribirse")
  parser.add_argument("cppm", help="Dirección IP del servidor ClearPass")
  parser.add_argument("user", help="Nombre del usuario api")
  parser.add_argument("secret", help="Client_secret del usuario api")
  parser.add_argument("nas_ip", nargs="*", help="IP del NAS (todo o parte)")
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
  if len(args.nas_ip) == 0:
    args.nas_ip = None

  loop = asyncio.get_event_loop()
  app = nats.App(args.url, (lambda: clearpass.session(cfg, verify=False)), verify=False)
  async def bootstrap():
    await app.start()
    await app.subscribe(args.topic, googleEnumerate(app, args.nas_ip))
  loop.run_until_complete(bootstrap())
  app.forever()
