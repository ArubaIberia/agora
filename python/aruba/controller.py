#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests

from aruba.errors import RequestError, FormatError
from aruba.common import _ask_input, _ask_pass, _fill, Config, Session
from contextlib import contextmanager


def _api_auth_url(api_host):
    return "https://{}:4343/v1/api".format(api_host)


def _api_config_url(api_host):
    return "https://{}:4343/v1/configuration".format(api_host)

# ------------------------
# Métodos de autenticación
# ------------------------


def _login(api_host, username, password, verify=True):
    """Lanza un intento de autenticación contra un MD/MM, devuelve el UIDARUBA"""
    login_url = _api_auth_url(api_host) + "/login"
    credentials = { "username": username, "password": password }
    response = requests.post(login_url, verify=verify, data=credentials)
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


def _logout(api_host, uidaruba, verify=True):
    """Cierra una sesion REST contra un MD/MM"""
    logout_url = _api_auth_url(api_host) + "/logout"
    credentials = { "UIDARUBA": uidaruba }
    response = requests.get(logout_url, verify=verify, data=credentials)
    if response.status_code != 200:
        raise RequestError(logout_url, None, credentials, response)


@contextmanager
def session(config, api_host=None, username=None, password=None, verify=True):
    """Obtiene un uidaruba para una MD/MM"""
    # Cargo de la config valores por defecto para todos los parámetros
    data = _fill({
        "api_host": api_host,
        "username": username,
        "password": password,
    }, config.get("controller"))
    # Saco las variables del array, por comodidad
    api_host, username, password = (
        data["api_host"],
        data["username"],
        data["password"],
    )
    # Lanzo la autenticacion que corresponda
    uidaruba = _login(api_host, username, password, verify=verify)
    try:
        yield Session(_api_config_url(api_host), uidaruba,
                      headers={ "Cookie": "SESSION={}".format(uidaruba) },
                      params={ "UIDARUBA": uidaruba })
    finally:
        _logout(api_host, uidaruba, verify=verify)


if __name__ == "__main__":

    # Cargo el fichero de configuracion y leo valores por defecto
    defaults = {
        "api_host": None,
        "username": None,
        "password": None
    }
    config = Config()
    defaults.update(config.get("controller"))

    # Solicito los datos básicos
    print("-" * 30 + " SETTINGS " + "-" * 30)
    data = {
        "api_host": _ask_input("Nombre del servidor", defaults["api_host"]),
        "username": _ask_input("Nombre de usuario", defaults["username"]),
        "password": _ask_pass("Password"),
    }

    # Pruebo la autenticación y guardo la config
    uidaruba = _login(data["api_host"], data["username"], data["password"], verify=False)
    try:
        print("OK! uidaruba = %s" % uidaruba)
        config.set("controller", data)
        config.save()
        print("Tokens guardados en %s" % config.path())
    finally:
        _logout(data["api_host"], uidaruba, verify=False)
