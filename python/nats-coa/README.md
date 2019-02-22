# NATS-CoA - Cliente para demos CoA con ClearPass

Este script se suscribe a un topic en un servidor [NATS](https://nats.io/). Por cada mensaje recibido en el topic, lanza una orden de CoA a ClearPass, a través de la API.

El script se utiliza en las demos de integración con Google Home. Cuando se le ordena a Google Assistant que ponga un dispositivo en cuarentena, manda un mensaje a la cola NATS para que este cliente lo reciba y lance el CoA.

[Esta otra aplicación](https://github.com/rafahpe/nats-gw) se encarga de enviar las peticiones de Google Assistant al topic de NATS.

## Configuración

El script necesitará un usuario API de ClearPass, con autenticación de tipo **client_credentials**. El perfil de operador asignado al usuario debe tener permisos para:

- Acceso a la API:
  - API Services > Allow API Access > Allow access
- Modificar atributos de endpoints:
  - Policy Manager > Identity - Endpoints > Read/Write
- Leer y terminar sesiones:
  - Guest Manager > Active Sessions > Full
  - Guest Manager > Active Sessions History > Read Only.

Las credenciales de este usuario API se le pasan al script dentro del cuerpo de cada mensaje que se empujan al topic (punto siguiente).

Esto se hizo así para simplificar poder usar un sólo cliente para varios ClearPass, a costa de la seguridad de las credenciales.

## Mensajes

El script espera leer del topic mensajes con este formato:

```json
{
  "host": "cppm-address",
  "user": "cppm-api-user",
  "pass": "cppm-api-key",
  "endpoint_mac": "endpoint MAC address",
  "nas_ip": "NAS IP address for CoA",
  "threat": true,
}
```

Cuando recibe un mensaje, hace lo siguiente:

- Si threat == true, actualiza el endpoint con estos dos atributos:
  - Threat Severity = Critical
  - Threat Status: In Progress
- Si threat == false, actualiza con:
  - Threat Severity = Critical
  - Threat Status: In Progress
- En ambos casos, localiza la última sesión del endpoint en el NAS indicado
- Manda un CoA Terminate Session al NAS.

## Docker

Este mismo directorio incluye un fichero [docker-compose](https://docs.docker.com/compose/) con los parámetros necesarios para arrancar el cliente. Para usar este servicio,

- Crea un archivo *.env* en este mismo directorio con dos atributos:

```env
NATS_URL=URL_del_servidor_NATS (ejemplo: tls://user:pass@nats.server.name:4222)
NATS_TOPIC=topic_de_NATS (ejemplo: cppm-coa)
```

- Y lanza el contenedor:

```bash
docker-compose run
```