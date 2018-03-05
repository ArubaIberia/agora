import xlwings as xw

import requests
from aruba import Config, switch


def vlans(data):
    """Enumera las VLANs del switch"""
    # Obtengo el workbook, las coordenadas y la dirección IP del servidor API
    wb, row, col, api_host = splitExcel(data)

    # Y ahora, obtengo los datos del switch
    with switch.session(Config(), api_host=api_host, verify=False) as session:
        vlans = requests.get(session.api_url + "/vlans", headers=session.headers(), verify=False)
        if vlans.status_code != 200:
            wb.sheets[0].range("%s%d"%(col, row)).value = "Error leyendo switch, "+vlans.text
            return
        for vlan in vlans.json()["vlan_element"]:
            wb.sheets[0].range(col+str(row)).value = "{} ({})".format(str(vlan["vlan_id"]), vlan["name"])
            row += 1


def splitExcel(data):
    """Des-serializa los datos recibidos de excel

    Por algún motivo, xlWings no me funciona bien si la funcion python a la
    que se llama desde VBA recibe más de un parámetro.

    Así que hasta que averigüe por qué, lo que estoy haciendo
    es serializar los datos. La función VBA tiene que pasar una
    cadena de texto con los siguientes parñametros, separados por ";":

    - Dirección IP / nombre al que se quiere conectar
    - Número de fila desde donde se invoca a esta funcion.
    - Nombre de columna desde donde se invoca a esta función

    Por ejemplo: "192.168.x.x;5;B"

    Esta función devuelve 4 objetos: el workbook, la fila, la columna, y la dirección.
    """
    # Los datos me vienen en formato direccion ; row ; col   ... cosas de VBA
    addr, row, col = data.split(";")
    addr = addr.strip() or None
    row = int(row)+1
    col = col.strip()

    # Borro toda la columna, desde la celda hacia abajo
    wb = xw.Book.caller()
    wb.sheets[0].range(col + str(row)).expand('down').clear_contents()

    # Y devuelvo workbook, fila, columna y direccion IP del api_host
    return (wb, row, col, addr)
