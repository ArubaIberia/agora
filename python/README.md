# Aruba Demo - funciones python para acceso a API

La libreria **aruba** ofrece funciones para simplificar el acceso a las APIs de switches, controladoras, ClearPass... cada una de las familias de dispositivos tiene un **módulo** dentro de la librería:

- *aruba.clearpass*
- *aruba.switch*
- *aruba.controller*
- Vendrán mas... (Central, Meridian, Instant...)

Para usar cada módulo, en primer lugar es necesario configurarlo con unas **credenciales**. Las credenciales son las que luego se usan para acceder a los dispositivos que gestiona el módulo (switches, controllers, etc).

La configuración de credenciales se hace a través de un pequeño asistente de línea de comandos que contiene cada módulo. Para lanzar el asistente de un módulo, se ejecuta con:

```
python -m aruba.<modulo>
```

Por ejemplo:

```
python -m aruba.clearpass
python -m aruba.controller
python -m aruba.switch
```

El asistente genera un fichero de configuración **.aruba.config** que se guarda en el directorio personal de cada usuario. Una vez configurado el módulo que se quiera usar, ya puede incluirse en cualquier script y utilizarse de manera sencilla, hay varios ejemplos en este directorio.
