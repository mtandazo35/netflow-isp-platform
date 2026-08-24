# Fuentes de identidad independientes

El motor NetFlow conserva todos los flujos y resuelve la identidad del cliente
mediante asignaciones temporales de IP. No necesita un sistema de facturacion.

## PPPoE

Fuentes soportadas por orden de preferencia:

1. Accounting de un servidor RADIUS estandar.
2. Consulta periodica de `/ppp/active` mediante RouterOS API.
3. Registro manual o importacion por API del proyecto.

Cada evento debe conservar usuario, IP, router, inicio, final,
`calling-station-id` y `acct-session-id` cuando existan.

## DHCP

Fuentes soportadas:

1. Leases obtenidos directamente de `/ip/dhcp-server/lease` mediante RouterOS API.
2. Eventos del DHCP server enviados por syslog o scripts RouterOS.
3. Importacion por API.

Se conserva IP, MAC, servidor DHCP, router, inicio y expiracion del lease.

## IP estatica

Las asignaciones se administran en la API del proyecto o se importan desde CSV.
Pueden tener fecha final o permanecer abiertas. Una IP estatica debe pertenecer
a un solo cliente durante un mismo intervalo temporal.

## Trafico sin identidad

Un flujo que atraviese el MikroTik se almacena aunque no exista asignacion. Se
marca con `subscriber_id=0` y `access_type=unknown`. Cuando aparece una asignacion
historica valida, un proceso de enriquecimiento puede volver a asociarlo.

## Regla temporal

La identidad se obtiene por:

```text
IP del flujo + router exportador + fecha/hora
```

El router exportador debe formar parte de la clave para soportar rangos privados
repetidos en nodos o redes diferentes.
