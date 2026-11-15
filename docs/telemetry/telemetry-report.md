# Brasaland - Reporte técnico de telemetría

## 1. Objetivo

Este reporte permite analizar la salud técnica y operativa de la aplicación Brasaland a partir de los eventos almacenados en `public.telemetry_events` de Supabase.

Complementa el documento `telemetry-plan.md`. No sustituye las métricas de negocio ni modifica el inventario.

## 2. Endpoint

GET /telemetry/report

Parámetros opcionales:

- `start_date`: fecha y hora ISO 8601.
- `end_date`: fecha y hora ISO 8601.

Si no se proporcionan fechas, se utiliza una ventana de los últimos siete días.

La respuesta tiene la estructura:

- `period.from`: inicio del intervalo.
- `period.to`: fin del intervalo.
- `metrics`: métricas técnicas calculadas.

El intervalo es semiabierto: incluye eventos con `timestamp >= start_date` y excluye eventos con `timestamp >= end_date`.

## 3. Métricas implementadas

### 3.1. events_per_day

Pregunta: ¿Cómo evoluciona el volumen de eventos registrados por día?

Agrupa los eventos por fecha UTC y devuelve la cantidad de eventos de cada día.

Permite detectar cambios bruscos de actividad o problemas de instrumentación.

### 3.2. error_rate_by_type

Pregunta: ¿Qué tipos de eventos presentan errores y en qué fechas?

Agrupa los eventos por día UTC y tipo de evento.

Calcula:

- `total_events`: eventos del grupo.
- `error_events`: eventos cuyo nivel es `error`.
- `error_rate`: porcentaje de errores del grupo.

La métrica no representa una tasa global de errores de toda la aplicación.

### 3.3. api_latency_by_endpoint

Pregunta: ¿Qué endpoints presentan mayor latencia media?

Analiza eventos `api_latency_recorded` y agrupa las mediciones válidas por `endpoint_id`.

Calcula:

- `request_count`: número de mediciones válidas.
- `average_latency_ms`: duración media en milisegundos.

Se excluyen duraciones inválidas o negativas.

## 4. Implementación

Las funciones de análisis están en `services/telemetry/analysis.py`.

Cada función:

- Consulta Supabase mediante SQL con parámetros de fecha.
- Convierte las fechas a UTC mediante Pandas.
- Utiliza operaciones de agrupación y agregación de Pandas.
- Devuelve estructuras compatibles con JSON.
- No escribe ni modifica eventos.

El endpoint se encuentra en `services/api/routers/telemetry.py`.

Implementa una caché en memoria de 60 segundos, identificada por el intervalo solicitado. Las fechas inválidas producen una respuesta HTTP 422 y los errores de consulta a la base de datos producen HTTP 503.

## 5. Evidencia de funcionamiento

El 15 de noviembre de 2026 se verificó el funcionamiento del endpoint contra los eventos almacenados en Supabase.

Una respuesta real del reporte incluyó:

- Eventos diarios: 3 eventos el 11 de noviembre y 661 el 15 de noviembre, para la ventana consultada.
- Latencia de `inventory`: 1 medición, con media de 125 ms.
- Tasas de error de 0 % en los grupos presentes en esa consulta.

Estos valores corresponden a una consulta concreta y cambiarán cuando se registren nuevos eventos.

También se verificaron 24 eventos técnicos posteriores a las 22:00 UTC del 15 de noviembre, correspondientes a navegación y carga de páginas del backoffice.

Las páginas observadas incluyeron `login`, `home`, `account_profile` e `incidents`.

Se detectaron eventos duplicados de carga y rutas incorrectas como `login**` e `incidents**`. Por tanto, el número de eventos no debe interpretarse como número de usuarios o acciones independientes.

## 6. Pruebas

La suite de pruebas del backend terminó con:

79 passed

Comando utilizado:

python -m pytest services/api/tests -q

Las pruebas del reporte cubren el cálculo de métricas, filtros temporales, fechas inválidas, zonas horarias, caché, errores de base de datos y ausencia de eventos.

También se comprobó que `/telemetry/events` y `/telemetry/report` aparecen en el esquema OpenAPI del servidor.

## 7. Limitaciones conocidas

- El evento `inbound_order_created` observado anteriormente contiene identificadores de prueba. No se presenta como evidencia de una operación de inventario auténtica.
- No se ha confirmado todavía un evento de error técnico real almacenado.
- Las rutas de listado y actualización de incidencias no están publicadas por el backend actual. Este problema es independiente del reporte de telemetría.
- La caché es local al proceso y no se comparte entre instancias del servidor.
- Las mediciones de latencia dependen de la disponibilidad de eventos `api_latency_recorded` con duraciones válidas.

## 8. Conclusión

El reporte técnico permite consultar el volumen diario de eventos, la proporción de errores por tipo y día, y la latencia media por endpoint.

La implementación utiliza consultas de solo lectura, agregaciones con Pandas, una ventana temporal coherente y una caché de 60 segundos.

La generación y verificación de eventos de negocio auténticos queda identificada como una comprobación pendiente.

## 9. Verificación final de Supabase

Consulta realizada el 15 de noviembre de 2026.

| Tipo de evento | Nivel | Registros |
|---|---|---:|
| `page_load_completed` | `info` | 454 |
| `page_viewed` | `info` | 232 |
| `api_latency_recorded` | `info` | 1 |
| `inbound_order_created` | `info` | 1 |
| **Total** | | **688** |

La base de datos contiene más de 20 eventos y se ha comprobado la captura real de navegación desde el backoffice.

El único evento `inbound_order_created` contiene los identificadores `test-order`, `test-product` y `test-location`. Se considera un registro de prueba y no acredita una transacción de inventario real.

No se encontraron eventos con nivel `error` en esta verificación. Por tanto, la métrica de errores está implementada y probada, pero todavía no se dispone de evidencia de un error técnico real almacenado.

Resultado final de pruebas automatizadas:

`79 passed in 8.50s`

Estas limitaciones quedan documentadas explícitamente y no se presentan como requisitos verificados.
