#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import configparser
import getpass
import os.path

from abc import ABC, abstractmethod
from typing import Mapping, Dict, Optional, Any, Iterator, Callable, cast

Settings = Mapping[str, Mapping[str, Any]]
Headers  = Optional[Dict[str, str]]
Attribs  = Optional[Dict[str, Any]]

# Nombre del fichero de settings donde se guardarán los tokens
SETTINGS_FILE = ".aruba.config"

class Config(Settings):

    """Interfaz para gestionar el acceso a las configuraciones"""

    def __init__(self, path: str = "~", filename: str = ".aruba.config") -> None:
        """Lee la configuración inicial de la ruta indicada"""
        configFile: str = os.path.join(os.path.expanduser(path), filename)
        config = configparser.ConfigParser()
        config.read(configFile)
        self._configFile = configFile
        self._config = config

    def __getitem__(self, section: str) -> Mapping[str, Any]:
        """Devuelve una seccion completa de la config, como un diccionario"""
        config = self._get_config()
        if not section in config.sections():
            return dict()
        return config[section]

    def __len__(self) -> int:
        return len(self._config)

    def __iter__(self) -> Iterator[str]:
        return iter(self._config)

    def set(self, section: str, data: Mapping[str, Any]) -> None:
        """Actualiza una sección de la config con un diccionario"""
        config = self._get_config()
        config.read_dict({section: data})

    def save(self) -> None:
        """Actualiza el fichero de config"""
        config = self._get_config()
        configFile = self._configFile
        if configFile is None:
            raise ValueError("No existe la ruta al fichero de config")
        with open(configFile, "w+") as f:
            config.write(f)

    def path(self) -> str:
        """Devuelve la ruta al fichero de config"""
        return self._configFile

    def _get_config(self) -> configparser.ConfigParser:
        config = self._config
        if config is None:
            raise ValueError("No se ha podido leer fichero de config")
        return config


class Session(ABC):

    """Objeto que encapsula la URL de la API, y el secreto de autenticación (token, cookie...)"""

    def __init__(self, api_url: str, secret: str, params: Attribs = None, headers: Headers = None):
        self.api_url = api_url
        self.secret = secret
        self._params = params
        self._headers = headers

    def params(self, params: Attribs = None) -> Attribs:
        """Añade a los argumentos dados, los necesarios para la autenticacion"""
        if not self._params:
            return params
        if not params:
            return self._params
        params.update(self._params)
        return params

    def headers(self, headers: Headers = None) -> Headers:
        """Añade a las cabeceras dadas, las necesarias para la autenticacion"""
        if not self._headers:
            return headers
        if not headers:
            return self._headers
        headers.update(self._headers)
        return headers

    @abstractmethod
    def refresh(self) -> None:
        raise NotImplemented()


def _ask_input(prompt: str, defaults: str = None) -> str:
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
    return cast(str, result)


def _ask_pass(prompt: str) -> str:
    """Pide un password por consola, ocultándolo si se puede"""
    prompt = "%s: " % prompt
    if sys.stdin.isatty():
        return getpass.getpass(prompt)
    return input(prompt)


def _fill(data: Dict, defaults: Optional[Mapping]) -> Mapping:
    """Sobreescribe en data los campos None con el campo del mismo nombre de defaults"""
    for key, val in data.items():
        if val is None:
            if defaults is None:
                raise KeyError(key)
            cached = defaults.get(key, None)
            if cached is None:
                raise KeyError(key)
            data[key] = cached
    return data

