#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests

from contextlib import contextmanager
from collections import namedtuple
from typing import Optional, Dict, Iterator, Any, cast

from aruba.errors import RequestError, FormatError
from aruba.common import _ask_input, _ask_pass, _fill, Config, Settings
from aruba import common


def _api_auth_url(api_host: str) -> str:
    return "https://{}:4343/v1/api".format(api_host)


def _api_config_url(api_host: str) -> str:
    return "https://{}:4343/v1/configuration".format(api_host)

# ------------------------
# Métodos de autenticación
# ------------------------


class Session(common.Session):

    def __init__(self, api_host: str, username: str, password: str, verify: bool = True) -> None:
        self._api_host = api_host
        self._username = username
        self._password = password
        self._verify = verify
        uidaruba = self._login()
        super().__init__(_api_config_url(api_host), uidaruba,
            headers={ "Cookie": f"SESSION={uidaruba}" },
            params={ "UIDARUBA": uidaruba })

    def _login(self) -> str:
        """Lanza un intento de autenticación contra un MD/MM, devuelve el UIDARUBA"""
        login_url = _api_auth_url(self._api_host) + "/login"
        credentials = { "username": self._username, "password": self._password }
        response = requests.post(login_url, verify=self._verify, data=credentials)
        if response.status_code != 200:
            raise RequestError(login_url, None, credentials, response)
        # No error, accedo a los tokens
        data = response.json()
        gres = data.get("_global_result", None)
        if not gres:
            raise FormatError(login_url, None, credentials, data, "_global_result")
        uid = gres.get("UIDARUBA", None)
        if not uid:
            raise FormatError(login_url, None, credentials, data, "UIDARUBA")
        return uid

    def _logout(self) -> None:
        """Cierra una sesion REST contra un MD/MM"""
        logout_url = _api_auth_url(self._api_host) + "/logout"
        credentials = { "UIDARUBA": self.secret }
        response = requests.get(logout_url, verify=self._verify, data=credentials)
        if response.status_code != 200:
            raise RequestError(logout_url, None, credentials, response)

    def refresh(self) -> None:
        uidaruba = self._login()
        headers = cast(Dict[str, str], self._headers)
        params = cast(Dict[str, Any], self._params)
        headers['Cookie'] = f"SESSION={uidaruba}"
        params["UIDARUBA"] = uidaruba
        self.secret = uidaruba


@contextmanager
def session(config: Settings, api_host: Optional[str] = None, username: Optional[str] = None,
    password: Optional[str] = None, verify: bool = True) -> Iterator[Session]:
    """Obtiene un uidaruba para una MD/MM"""
    # Cargo de la config valores por defecto para todos los parámetros
    data = _fill({
        "api_host": api_host,
        "username": username,
        "password": password,
    }, config.get("controller"))
    # Saco las variables del array, por comodidad
    Params = namedtuple('Params', ('api_host', 'username', 'password'))
    asserted = Params(data["api_host"], data["username"], data["password"])
    # Lanzo la autenticacion que corresponda
    curr = Session(asserted.api_host, asserted.username, asserted.password, verify=verify)
    try:
        yield curr
    finally:
        curr._logout()


if __name__ == "__main__":

    # Cargo el fichero de configuracion y leo valores por defecto
    defaults = {
        "api_host": None,
        "username": None,
        "password": None
    }
    config = Config()
    controller = config.get('controller')
    if controller is not None:
        defaults.update(controller)

    # Solicito los datos básicos
    print("-" * 30 + " SETTINGS " + "-" * 30)
    data = {
        "api_host": _ask_input("Nombre del servidor", defaults["api_host"]),
        "username": _ask_input("Nombre de usuario", defaults["username"]),
        "password": _ask_pass("Password"),
    }

    # Pruebo la autenticación y guardo la config
    config.set("controller", data)
    with session(config, verify=False) as curr:
        print(f"OK! uidaruba = {curr.secret}")
        config.save()
        print(f"Tokens guardados en {config.path()}")
