#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import sys
import json

# Ejemplo de autenticación básica, sin usar el módulo Aruba.
# Realiza una conexión REST a un switch y lee la lista de VLANs

host_add = "192.168.XX.XX"
username = "XXXX"
password = "XXXX"

# Desactivo el log de certificado autofirmado. Ya sé que mis switches
# tienen certificado autofirmado.

import logging
logging.captureWarnings(True)

# Primer paso: construir la URL de la API a partir de la IP del switch
url_api = "https://{ip}/rest/v4".format(ip=host_add)

# Segundo paso: Autenticar al usuario
response = requests.post(url_api + "/login-sessions", verify=False, json={
    "userName": username,
    "password": password
})
if response.status_code != 201:
    print("Error de autenticación: ", response.text)
    sys.exit(-1)

# Tercer paso: Obtener la cookie que hay que añadir a todas las cabeceras
data = response.json()
headers = { "Cookie": data["cookie"] }

# Cuarto paso: Hacer lo que haga falta
response = requests.get(url_api + "/vlans", verify=False, headers=headers)
if response.status_code != 200:
    print("Error leyendo VLANs: ", response.status_code, response.text)
    sys.exit(-1)
print(json.dumps(response.json(), indent=4))

# último paso: cerrar sesión
response = requests.delete(url_api + "/login-sessions", verify=False, headers=headers)
if response.status_code != 204:
    print("Error de cierre de sesion: ", response.text)

