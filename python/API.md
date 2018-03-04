# REST APIs

## ClearPass

### Acceso a la API:

- [https://clearpass.arubademo.net/guest] : Obtener token
- [https://clearpass.arubademo.net/api-docs] : Interfaz swagger
- [https://clearpass.arubademo.net/api] : API

### Autenticación

POST [https://clearpass.arubademo.net/api/oauth]

- API Key:
```
{
  "grant_type":    "client_credentials",
  "client_id":     "{{ client_id }}",
  "client_secret": "{{ client_secret }}"
}
```

- User Password:
```
{
  "grant_type":    "username",
  "client_id":     "{{ client_id }}",
  "client_secret": "{{ client_secret }}",
  "username":      "{{ username }}",
  "password":      "{{ password }}"
}
```

- Refresh token:
```
{
  "grant_type":    "refresh_token",
  "client_id":     "{{ client_id }}",
  "client_secret": "{{ client_secret }}",
  "refresh_token": "{{ refresh_token }}"
}
```

### Documentación:

- (ClearPass REST APIs)[http://support.arubanetworks.com/Documentation/tabid/77/DMXModule/512/Command/Core_Download/Method/attachment/Default.aspx?EntryId=22490]

## ArubaOS-Switch

### Acceso a la API:

- https://{{switch}}/rest/v3 : API

### Autenticación

POST https://{{switch}}/rest/v3/login-sessions
```
{
  "userName":    "{{switch_username}}",
  "password":    "{{switch_password}}"
}
```

### Documentación:

- (Aruba REST APIs - 16.05)[https://support.hpe.com/hpsc/doc/public/display?sp4ts.oid=1008995295&docLocale=en_US&docId=emr_na-a00040422en_us]
