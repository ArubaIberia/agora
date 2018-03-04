#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import requests

from aruba.errors import RequestError, FormatError
from aruba.common import _ask_input, _ask_pass, _fill, Config, Session
from contextlib import contextmanager


def _api_url(api_host):
    return "https://{}/rest/v3".format(api_host)

# ------------------------
# Métodos de autenticación
# ------------------------


def _login(api_host, username, password, verify=True):
    """Lanza un intento de autenticación contra un switch, devuelve la cookie"""
    login_url = _api_url(api_host) + "/login-sessions"
    credentials = { "userName": username, "password": password }
    response = requests.post(login_url, verify=verify, json=credentials)
    if response.status_code != 201:
        raise RequestError(login_url, None, credentials, response)
    # No error, accedo a los tokens
    data = response.json()
    cookie = data.get("cookie", None)
    if not cookie:
        raise FormatError(login_url, None, credentials, data, "cookie")
    return cookie


def _logout(api_host, cookie, verify=True):
    """Cierra una sesion REST contra un switch"""
    logout_url = _api_url(api_host) + "/login-sessions"
    headers = { "Cookie": cookie }
    response = requests.delete(logout_url, verify=verify, headers=headers)
    if response.status_code != 204:
        raise RequestError(logout_url, headers, None, response)


@contextmanager
def session(config, api_host=None, username=None, password=None, verify=True):
    """Obtiene una cookie para un switch"""
    # Cargo de la config valores por defecto para todos los parámetros
    data = _fill({
        "api_host": api_host,
        "username": username,
        "password": password,
    }, config.get("switch"))
    # Saco las variables del array, por comodidad
    api_host, username, password = (
        data["api_host"],
        data["username"],
        data["password"],
    )
    # Lanzo la autenticacion que corresponda
    cookie = _login(api_host, username, password, verify=verify)
    try:
        yield Session(_api_url(api_host), cookie, headers={ "Cookie": cookie })
    finally:
        _logout(api_host, cookie, verify=verify)


if __name__ == "__main__":

    # Cargo el fichero de configuracion y leo valores por defecto
    defaults = {
        "api_host": None,
        "username": None,
        "password": None
    }
    config = Config()
    defaults.update(config.get("switch"))

    # Solicito los datos básicos
    print("-" * 30 + " SETTINGS " + "-" * 30)
    data = {
        "api_host": _ask_input("Nombre del servidor", defaults["api_host"]),
        "username": _ask_input("Nombre de usuario", defaults["username"]),
        "password": _ask_pass("Password"),
    }

    # Pruebo la autenticación y giardo la config
    cookie = _login(data["api_host"], data["username"], data["password"], verify=False)
    try:
        print("OK! cookie = %s" % cookie)
        config.set("switch", data)
        config.save()
        print("Tokens guardados en %s" % config.path())
    finally:
        _logout(data["api_host"], cookie, verify=False)
