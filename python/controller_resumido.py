#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import requests
import json

from aruba import Config, controller

# Ejemplo de conexión básica, con módulo Aruba.
# Realiza una conexión REST a un controller.

# Desactivo el log de certificado autofirmado.
import logging
logging.captureWarnings(True)

# Inicio una sesión con el MM/MD que está en el fichero de configuración.
# Para cambiar las credenciales: python -m aruba.controller

with controller.session(Config(), verify=False) as session:

    # Solo tenemos que hacer lo que queremos hacer!
    # El context-manager se ocupa de lo demás
    response = requests.get(session.api_url + "/object/ap_prov", headers=session.headers(), params=session.params({ "config-path": "/md" }), verify=False)
    if response.status_code != 200:
        print("Error leyendo APs: ", response.status_code, response.text)
        sys.exit(-1)
    print(json.dumps(response.json(), indent=4))

