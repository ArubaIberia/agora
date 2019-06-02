#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import requests

from contextlib import contextmanager
from collections import namedtuple
from typing import Dict, Mapping, Optional, Iterator, cast

from aruba.errors import RequestError, FormatError
from aruba.common import _ask_input, _ask_pass, _fill, Config, Settings
from aruba import common


def _api_url(api_host: str) -> str:
    """Obtiene la URL de la API de clearpass, a partir del hostname"""
    return "https://{}/api".format(api_host)

# ------------------------
# Métodos de autenticación
# ------------------------

class Session(common.Session):

    def __init__(self, grant_type: str, api_host: str, client_id: str, client_secret: str,
        username: str, password: str, verify: bool = True) -> None:
        self._api_host: str = api_host
        self._grant_type: str = grant_type
        self._client_id: str = client_id
        self._client_secret: str = client_secret
        self._username: str = username
        self._password: str = password
        self._verify: bool = verify
        self._refresh_token: Optional[str] = None
        token = self._auth()
        headers = { "Authorization": f"Bearer {token}" }
        super().__init__(_api_url(api_host), token, headers=headers)

    def _auth_request(self, attrib: str, credentials: Mapping[str, str]) -> str:
        oauth_url = _api_url(self._api_host) + "/oauth"
        response = requests.post(oauth_url, verify=self._verify, json=credentials)
        if response.status_code != 200:
            raise RequestError(oauth_url, None, credentials, response)
        # No error, accedo a los tokens
        data = response.json()
        if not attrib in data:
            raise FormatError(oauth_url, None, credentials, data, attrib)
        return data[attrib]

    def _client_auth(self) -> str:
        return self._auth_request("access_token", {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        })

    def _password_auth(self) -> str:
        """Obtiene un refresh_token para el tipo de autenticacion password"""
        return self._auth_request("refresh_token", {
            "grant_type": "password",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "username": self._username,
            "password": self._password,
        })

    def _refresh_auth(self) -> str:
        assert(self._refresh_token is not None)
        return self._auth_request("access_token", {
            "grant_type": "refresh_token",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "refresh_token": self._refresh_token,
        })

    def _auth(self) -> str:
        "Autentica la sesion, almacena el refresh token más reciente"
        # Si el grant_type es client_credentials, autentico tal cual
        if self._grant_type == "client_credentials":
            return self._client_auth()
        # Si tengo un refresh token, intento utilizarlo
        if self._refresh_token is not None:
            try:
                return self._refresh_auth()
            except RequestError:
                pass
        # Si no tengo refresh o no funciona, autentico con password
        self._refresh_token = self._password_auth()
        if self._refresh_token is None:
            raise ValueError("Invalid credentials for password authentication")
        return self._refresh_auth()

    def refresh(self) -> None:
        token = self._auth()
        headers = cast(Dict[str, str], self._headers)
        headers["Authorization"] = f"Bearer {token}"
        self.secret = token


@contextmanager
def session(config: Settings, grant_type: Optional[str] = None, api_host: Optional[str] = None,
    client_id: Optional[str] = None, client_secret: Optional[str] = None,
    username: Optional[str] = None, password: Optional[str] = None, verify: bool = True) -> Iterator[Session]:
    """Obtiene un token para ClearPass. Si grant_type=="password", necesita un refresh_token en la config"""
    # Cargo de la config valores por defecto para todos los parámetros
    defaults = config["clearpass"]
    provided = _fill({
        "grant_type": grant_type,
        "api_host": api_host,
        "client_id": client_id,
        "client_secret": client_secret,
    }, defaults)
    # Si la autenticacion no es tipo client_credentials, el username es obligatorio
    str_username, str_password = "", ""
    if (provided["grant_type"] != "client_credentials"):
        username = username if username is not None and username != "" else defaults["username"]
        password = password if password is not None and password != "" else defaults.get("password", None)
        if (username is None) or (username == "") or (password is None) or (password == ""):
            raise ValueError("Missing username or password for authentication")
        str_username = cast(str, username)
        str_password = cast(str, password)
    # Meto todos los valores en una estructura, por comodidad
    Params = namedtuple('Params', ('username', 'password', 'grant_type', 'api_host', 'client_id', 'client_secret'))
    asserted = Params(
        str_username, str_password, provided["grant_type"], provided["api_host"],
        provided["client_id"], provided["client_secret"]
    )
    # Todo OK, podemos autenticar
    yield Session(asserted.grant_type, asserted.api_host,  asserted.client_id, asserted.client_secret,
        asserted.username, asserted.password, verify)


if __name__ == "__main__":

    # Cargo el fichero de configuracion y actualizo valores por defecto
    defaults =  {
        "grant_type": None,
        "api_host": None,
        "client_id": None,
        "client_secret": None,
        "username": None,
    }
    config = Config()
    defaults.update(config["clearpass"])

    # Solicito los datos básicos
    print("-" * 30 + " SETTINGS " + "-" * 30)
    data = {
        "grant_type":    "client_credentials",
        "api_host":      _ask_input("Nombre del servidor", defaults["api_host"]),
        "client_id":     _ask_input("ID de aplicación (client_id)", defaults["client_id"]),
        "client_secret": _ask_pass("Password de aplicación"),
        "username":      "",
        "password":      "",
    }

    # Si la autenticación es password, necesito el refresh_token
    selection = _ask_input("¿Necesita introducir usuario y password? [S/N]")
    if selection.lower() in ("s", "si", "sí", "y", "yes"):
        username = _ask_input("Escribe el nombre de usuario (username)")
        password = _ask_pass("Escribe el password de usuario")
        data["grant_type"] = "password"
        data["username"] = username
        data["password"] = password

    config.set("clearpass", data)
    with session(config, verify=False) as curr:
        # Inicio sesion para validar credenciales y obtener refresh_token
        if curr._refresh_token is not None:
            data["refresh_token"] = curr._refresh_token
            config.set("clearpass", data)
        token = curr.secret
        # Actualizo la configuración
        print(f"OK! token = {token}")
        config.save()
        print(f"Tokens guardados en {config.path()}")
