# NetFlow ISP Analytics

Plataforma independiente en desarrollo para correlacionar NetFlow/IPFIX, asignaciones de clientes y DNS. El objetivo es medir consumo por abonado, dominio y aplicacion, y detectar patrones de uso sostenido que requieran revision operativa.

El proyecto no depende de Mikrowisp ni de otra plataforma de facturacion. Puede
trabajar directamente con MikroTik RouterOS, RADIUS estandar y registros
administrados por su propia API.

> Estado: MVP inicial. Todavia no debe conectarse a produccion.

## Primer arranque

```bash
cp .env.example .env
# Cambie todas las contrasenas de .env
docker compose up -d --build
curl http://localhost:8080/health
```

El panel queda disponible en `http://IP_DEL_SERVIDOR:8081` y la documentacion
interactiva de la API en `http://IP_DEL_SERVIDOR:8080/docs`.

Configure cada MikroTik para enviar NetFlow v9 al servidor:

```routeros
/ip traffic-flow set enabled=yes interfaces=all active-flow-timeout=1m inactive-flow-timeout=15s
/ip traffic-flow target add dst-address=IP_DEL_SERVIDOR port=9996 version=9
```

Para produccion, sustituya `interfaces=all` por las interfaces verificadas durante
la prueba para evitar doble contabilizacion.

Los flujos se muestran por IP aunque no exista un inventario. Para presentar el
nombre, plan y tipo de acceso, edite `config/subscribers.json`:

```json
{
  "subscribers": [
    {
      "id": 500,
      "name": "Pedro Lopez",
      "ip": "10.10.0.10",
      "exporter_ip": "10.8.0.2",
      "plan_mbps": 100,
      "access_type": "static"
    }
  ]
}
```

La clave `exporter_ip` evita confundir rangos privados repetidos entre routers.

Para cargar 24 horas de trafico simulado de tres clientes (PPPoE, DHCP y
estatico), ejecute:

```bash
python3 tools/simulate_traffic.py \
  --api-url http://localhost:8080 \
  --api-key replace-with-a-long-random-value \
  --hours 24
```

Luego consulte:

```bash
curl "http://localhost:8080/api/v1/analytics/top-subscribers?hours=24"
curl "http://localhost:8080/api/v1/analytics/resale-candidates?hours=24"
```

## Pruebas simuladas

Las pruebas no necesitan un MikroTik real. Simulan flujos normalizados, dominios,
consumo y patrones residenciales frente a saturacion sostenida:

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements-dev.txt
cd backend
../.venv/bin/pytest -q
```

## Componentes actuales

- ClickHouse para flujos y respuestas DNS.
- PostgreSQL para routers, abonados y asignaciones historicas PPPoE, DHCP y estaticas.
- Colector `nfcapd` en UDP 9996.
- Procesador automatico de archivos con checkpoint persistente.
- API FastAPI para ingreso normalizado y consultas iniciales.
- Panel web local con resumen, principales consumidores, destinos y riesgo.
- Normalizador de salida NDJSON de nfdump.
- Asignacion temporal de flujos a clientes PPPoE, DHCP o IP estatica, incluso con IP reutilizada.
- Correlacion DNS por cliente, respuesta, horario y TTL.
- Clasificacion inicial de YouTube, Netflix, TikTok y Meta.
- Retencion inicial: 90 dias para flujos y 30 dias para eventos DNS.
- Consulta de principales consumidores.
- Consulta de dominios por abonado.
- Indicador preliminar de posibles patrones de reventa.

## Limites de interpretacion

- El tiempo por dominio representa actividad de red, no tiempo visible en pantalla.
- La atribucion de dominio es aproximada y debe indicar confianza.
- DoH, DoT, VPN, CDN compartidas y ECH pueden impedir una atribucion exacta.
- El indicador de reventa no constituye prueba y debe revisarse junto con otras evidencias.

## Proximos componentes

1. Ejecutor `nfdump -> NDJSON -> pipeline -> API` con checkpoints e idempotencia.
2. Sincronizacion directa con RouterOS API y RADIUS estandar para sesiones historicas.
3. Adaptadores de logs para Technitium, AdGuard y Unbound.
4. Catalogo ampliado de aplicaciones, ASN y CDN.
5. Dashboard web y configuracion de routers.

La ingenieria inversa original se conserva exclusivamente como referencia historica en
[netflow-arquitectura.md](netflow-arquitectura.md); sus componentes no son dependencias
del producto nuevo.
