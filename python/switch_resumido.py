#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import sys
from aruba import Config, switch
import json

# Ejemplo de autenticación básica, con módulo Aruba.
# Realiza una conexión REST a un switch y lee la lista de VLANs

# Desactivo el log de certificado autofirmado. Ya sé que mis switches
# tienen certificado autofirmado.
import logging
logging.captureWarnings(True)

# Inicio una sesión con el switch que está almacenado en el fichero de configuración.
# Para cambiar las credenciales: python -m aruba.switches

with switch.session(Config(), verify=False) as session:

    # Solo tenemos que hacer lo que queremos hacer!
    # El context-manager se ocupa de lo demás
    response = requests.get(session.api_url + "/vlans", verify=False, headers=session.headers())
    if response.status_code != 200:
        print("Error leyendo VLANs: ", response.status_code, response.text)
        sys.exit(-1)
    print(json.dumps(response.json(), indent=4))
