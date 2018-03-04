#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json


class RequestError(Exception):

    """ Error que se genera cuando hay un fallo accediendo al servidor"""

    def __init__(self, url, headers, body, response):
        self.url = url
        self.headers = headers
        self.body = body
        self.status_code = response.status_code
        self.text = response.text
        self.response = response
        super().__init__(self.message())

    def message(self):
        return "code {}, body: {}".format(self.status_code, self.text)


class FormatError(Exception):

    """Error que se genera cuando la respuesta recibida del servidor no tiene el formato correcto"""
    def __init__(self, url, headers, body, json, key):
        self.url = url
        self.headers = headers
        self.body = body
        self.json = json
        self.key = key
        super().__init__(self.message())

    def message(self):
        return "missing key: {}, body: {}".format(self.key, json.dumps(self.json, indent=4))
