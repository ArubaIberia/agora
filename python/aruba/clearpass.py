#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import requests

from aruba.errors import RequestError, FormatError
from aruba.common import _ask_input, _ask_pass, _fill, Config, Session
from contextlib import contextmanager


def _api_url(api_host):
    """Obtiene la URL de la API de clearpass, a partir del hostname"""
    return "https://{}/api".format(api_host)

# ------------------------
# Métodos de autenticación
# ------------------------


def _auth(api_host, attrib, credentials, verify=True):
    oauth_url = _api_url(api_host) + "/oauth"
    response = requests.post(oauth_url, verify=verify, json=credentials)
    if response.status_code != 200:
        raise RequestError(oauth_url, None, credentials, response)
    # No error, accedo a los tokens
    data = response.json()
    if not attrib in data:
        raise FormatError(oauth_url, None, credentials, data, attrib)
    return data[attrib]


def _client_auth(api_host, client_id, client_secret, verify=True):
    return _auth(api_host, "access_token", {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }, verify=verify)


def _password_auth(api_host, client_id, client_secret, username, password, verify=True):
    """Obtiene un refresh_token para el tipo de autenticacion password"""
    return _auth(api_host, "refresh_token", {
        "grant_type": "password",
        "client_id": client_id,
        "client_secret": client_secret,
        "username": username,
        "password": password,
    }, verify)


def _refresh_auth(api_host, client_id, client_secret, refresh_token, verify=True):
    return _auth(api_host, "access_token", {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
    }, verify=verify)


@contextmanager
def session(config, grant_type=None, api_host=None, client_id=None, client_secret=None, username=None, password=None, verify=True):
    """Obtiene un token para ClearPass. Si grant_type=="password", necesita un refresh_token en la config"""
    # Cargo de la config valores por defecto para todos los parámetros
    defaults = config.get("clearpass")
    provided = _fill({
        "grant_type": grant_type,
        "api_host": api_host,
        "client_id": client_id,
        "client_secret": client_secret,
    }, defaults)
    # Si la autenticacion no es tipo client_credentials, el username es obligatorio
    if (provided["grant_type"] != "client_credentials"):
        username = username if username is not None else defaults["username"]
        password = password if password is not None else defaults.get("password", None)
    # Saco las variables del array, por comodidad
    grant_type, api_host, client_id, client_secret, refresh_token = (
        provided["grant_type"],
        provided["api_host"],
        provided["client_id"],
        provided["client_secret"],
        defaults.get("refresh_token", None),
    )
    def auth(mem=[refresh_token]):
        "Autentica la sesion, almacena el refresh token más reciente"
        # Si el grant_type es client_credentials, autentico tal cual
        if grant_type == "client_credentials":
            return _client_auth(api_host, client_id, client_secret, verify=verify)
        # Si tengo un refresh token, intento utilizarlo
        refresh_token = mem[0]
        if refresh_token is not None:
            try:
                return _refresh_auth(api_host, client_id, client_secret, refresh_token, verify=verify)
            except RequestError:
                pass
        # Si no tengo refresh o no funciona, autentico con password
        mem[0] = _password_auth(api_host, client_id, client_secret, username, password, verify=verify)
        return _refresh_auth(api_host, client_id, client_secret, mem[0], verify=verify)
    # Authenticate and create session
    token = auth()
    result = Session(_api_url(api_host), token, headers={ "Authorization": "Bearer {}".format(token) })
    # Add refresh() closure to session
    def refresh():
        token = auth()
        result.headers["Authorization"] = "Bearer {}".format(token)
        result.secret = token
    result.refresh = refresh
    yield result


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
    defaults.update(config.get("clearpass"))

    # Solicito los datos básicos
    print("-" * 30 + " SETTINGS " + "-" * 30)
    data = {
        "grant_type":    "client_credentials",
        "api_host":      _ask_input("Nombre del servidor", defaults["api_host"]),
        "client_id":     _ask_input("ID de aplicación (client_id)", defaults["client_id"]),
        "client_secret": _ask_pass("Password de aplicación"),
    }

    # Si la autenticación es password, necesito el refresh_token
    selection = _ask_input("¿Necesita introducir usuario y password? [S/N]")
    if selection.lower() in ("s", "si", "sí", "y", "yes"):
        username = _ask_input("Escribe el nombre de usuario (username)")
        password = _ask_pass("Escribe el password de usuario")
        token = _password_auth(data["api_host"], data["client_id"], data["client_secret"], username, password, False)
        data["grant_type"] = "password"
        data["username"] = username
        data["refresh_token"] = token
    else:
        token = _client_auth(data["api_host"], data["client_id"], data["client_secret"], False)

    # Actualizo la configuración
    print("OK! token = %s" % token)
    config.set("clearpass", data)
    config.save()
    print("Tokens guardados en %s" % config.path())
