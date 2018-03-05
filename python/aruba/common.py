#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import configparser
import getpass
import os.path

# Nombre del fichero de settings donde se guardarán los tokens
SETTINGS_FILE = ".aruba.config"


class Config(object):

    """Interfaz para gestionar el acceso a las configuraciones"""

    def __init__(self, path="~", filename=".aruba.config"):
        """Lee la configuración inicial de la ruta indicada"""
        self._configFile, self._config = None, None
        configFile = os.path.join(os.path.expanduser(path), filename)
        config = configparser.ConfigParser()
        config.read(configFile)
        self._configFile = configFile
        self._config = config

    def get(self, section):
        """Devuelve una seccion completa de la config, como un diccionario"""
        config = self._get_config()
        if not section in config.sections():
            return dict()
        return config[section]

    def set(self, section, data):
        """Actualiza una sección de la config con un diccionario"""
        config = self._get_config()
        config.read_dict({section: data})

    def save(self):
        """Actualiza el fichero de config"""
        config = self._get_config()
        configFile = self._configFile
        if configFile is None:
            raise ValueError("No existe la ruta al fichero de config")
        with open(configFile, "w+") as f:
            config.write(f)

    def path(self):
        """Devuelve la ruta al fichero de config"""
        return self._configFile

    def _get_config(self):
        config = self._config
        if config is None:
            raise ValueError("No se ha podido leer fichero de config")
        return config


class Session(object):

    """Objeto que encapsula la URL de la API, y el secreto de autenticación (token, cookie...)"""

    def __init__(self, api_url, secret, params=None, headers=None):
        self.api_url = api_url
        self.secret = secret
        self._params = params
        self._headers = headers

    def params(self, params=None):
        """Añade a los argumentos dados, los necesarios para la autenticacion"""
        if not self._params:
            return params
        if not params:
            return self._params
        params.update(self._params)
        return params

    def headers(self, headers=None):
        """Añade a las cabeceras dadas, las necesarias para la autenticacion"""
        if not self._headers:
            return headers
        if not headers:
            return self._headers
        headers.update(self._headers)
        return headers


def _ask_input(prompt, defaults=None):
    """Pide una entrada por consola. Si defaults != None, lo utiliza como valor por defecto."""
    result = None
    while result is None:
        if defaults is not None:
            result = input("%s [%s]: " % (prompt, defaults))
        else:
            result = input("%s: " % prompt)
        if result == "":
            if defaults is None:
                print("Debe introducir un valor para: %s" % prompt)
                result = None
            else:
                result = defaults
    return result


def _ask_pass(prompt):
    """Pide un password por consola, ocultándolo si se puede"""
    prompt = "%s: " % prompt
    if sys.stdin.isatty():
        return getpass.getpass(prompt)
    return input(prompt)


def _fill(data, defaults):
    """Sobreescribe en data los campos None con el campo del mismo nombre de defaults"""
    for key, val in data.items():
        if val is None:
            cached = defaults.get(key, None)
            if cached is None:
                raise KeyError(key)
            data[key] = cached
    return data

