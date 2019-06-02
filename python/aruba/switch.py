#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import requests

from contextlib import contextmanager
from collections import namedtuple
from typing import Optional, Dict, Iterator, cast

from aruba.errors import RequestError, FormatError
from aruba.common import _ask_input, _ask_pass, _fill, Config, Settings
from aruba import common


def _api_url(api_host: str, api_version: str) -> str:
    return "https://{}/rest/{}".format(api_host, api_version)

# ------------------------
# Métodos de autenticación
# ------------------------

class Session(common.Session):

    def __init__(self, api_host: str, api_version: str, username: str, password: str, verify: bool = True) -> None:
        self._api_host = api_host
        self._api_version = api_version
        self._username = username
        self._password = password
        self._verify = verify
        api_url = _api_url(self._api_host, self._api_version)
        cookie = self._login(api_url)
        super().__init__(api_url, cookie, headers={'Cookie': cookie})

    def _login(self, api_url: str) -> str:
        """Lanza un intento de autenticación contra un switch, devuelve la cookie"""
        login_url = api_url + "/login-sessions"
        credentials = { "userName": self._username, "password": self._password }
        response = requests.post(login_url, verify=self._verify, json=credentials)
        if response.status_code != 201:
            raise RequestError(login_url, None, credentials, response)
        # No error, accedo a los tokens
        data = response.json()
        cookie = data.get("cookie", None)
        if not cookie:
            raise FormatError(login_url, None, credentials, data, "cookie")
        return cookie

    def _logout(self) -> None:
        """Cierra una sesion REST contra un switch"""
        logout_url = self.api_url + "/login-sessions"
        response = requests.delete(logout_url, verify=self._verify, headers=self._headers)
        if response.status_code != 204:
            raise RequestError(logout_url, self._headers, None, response)

    def refresh(self) -> None:
        cookie = self._login(self.api_url)
        headers = cast(Dict[str, str], self._headers)
        headers['Cookie'] = cookie
        self.secret = cookie


@contextmanager
def session(config: Settings, api_host: Optional[str] = None, api_version: Optional[str] = None,
    username: Optional[str] = None, password: Optional[str] = None, verify: bool = True) -> Iterator[Session]:
    """Obtiene una cookie para un switch"""
    # Cargo de la config valores por defecto para todos los parámetros
    data = _fill({
        "api_host": api_host,
        "username": username,
        "password": password,
        "api_version": api_version,
    }, config.get("switch"))
    # Saco las variables del array, por comodidad
    Params = namedtuple('Params', ('api_host', 'username', 'password', 'api_version'))
    asserted = Params(
        data["api_host"], data["username"], data["password"], data["api_version"]
    )
    # Lanzo la autenticacion que corresponda
    curr = Session(asserted.api_host, asserted.api_version, asserted.username, asserted.password, verify)
    try:
        yield curr
    finally:
        curr._logout()


if __name__ == "__main__":

    # Cargo el fichero de configuracion y leo valores por defecto
    defaults = {
        "api_host": None,
        "username": None,
        "password": None,
        "api_version": "v4",
    }
    config = Config()
    switch = config.get('switch')
    if switch is not None:
        defaults.update(switch)

    # Solicito los datos básicos
    print("-" * 30 + " SETTINGS " + "-" * 30)
    data = {
        "api_host": _ask_input("Nombre del servidor", defaults["api_host"]),
        "username": _ask_input("Nombre de usuario", defaults["username"]),
        "password": _ask_pass("Password"),
        "api_version": _ask_input("Version de la API", defaults["api_version"]),
    }

    # Pruebo la autenticación y giardo la config
    config.set("switch", data)
    with session(config, verify=False) as curr:
        print(f"OK! cookie = {curr.secret}")
        config.save()
        print(f"Tokens guardados en {config.path()}")
