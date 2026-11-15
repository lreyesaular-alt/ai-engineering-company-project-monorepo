# Brasaland - Plan de Telemetría

## 1. Propósito y alcance

Este documento define el diseño de telemetría de Brasaland para identificar qué información del sistema de inventario y del resto de la aplicación debe capturarse, cómo debe estructurarse y qué decisiones puede facilitar.

El objetivo es que el equipo técnico pueda instrumentar el sistema sin necesitar aclaraciones adicionales.

La telemetría debe cubrir tanto las métricas obligatorias del negocio como las oportunidades adicionales de observabilidad técnica y operativa.

Este entregable es un documento de diseño. No implementa instrumentación, no crea infraestructura de almacenamiento y no modifica el comportamiento de la aplicación.

## 2. Contexto empresarial

Brasaland es una cadena de restaurantes de comida a la brasa con 14 locales entre Colombia y Florida.

El sistema de gestión de inventario se utiliza para controlar ingredientes como carnes, vegetales, salsas, bebidas y empaques. El sistema está en producción.

### 2.1. Entidades principales

| Entidad | Significado |
|---|---|
| `Product` | Ingrediente o insumo, con unidad de medida y categoría. |
| `InboundOrder` | Orden de entrada de mercancía recibida de un proveedor en un local. |
| `OutboundOrder` | Orden de salida asociada al consumo de ingredientes o al registro de merma. |
| `location` | Local identificado por país y ciudad. |
| `supplier` | Proveedor de Brasaland, diferenciado por país. |

### 2.2. Restricciones del negocio

- Brasaland dispone de 14 locales entre Colombia y Florida.
- Colombia utiliza `CO` y `COP`.
- Florida utiliza `US` y `USD`.
- Los importes deben conservar la moneda local.
- La telemetría no debe convertir monedas.
- El stock nunca se modifica directamente.
- Toda modificación de stock debe realizarse mediante `InboundOrder` u `OutboundOrder` y ser trazable.
- Los motivos de merma permitidos son `expired`, `kitchen_error` y `theft_suspected`.
- No deben incluirse nombres de empleados ni datos de clientes en las propiedades de los eventos.

## 3. Objetivos de medición

El plan debe permitir responder preguntas como:

- ¿Cuántas órdenes de entrada y salida se registran por local y por día?
- ¿Qué productos se consumen con mayor frecuencia?
- ¿Qué productos acumulan más errores de validación?
- ¿Cuánto stock se pierde y por qué motivo?
- ¿En qué locales se activan más alertas de stock mínimo?
- ¿Cuántos intentos de modificación directa del stock son rechazados?
- ¿Qué ingredientes presentan variaciones de precio relevantes?
- ¿Cuántos intentos de autenticación fallan?
- ¿Cuándo expiran las sesiones?
- ¿Qué secciones del backoffice se visitan con mayor frecuencia?
- ¿Qué flujos se abandonan antes de completarse?
- ¿Qué errores de frontend y backend se producen?
- ¿Cuánto tardan las solicitudes de API y las cargas de páginas?

## 4. Convenciones de eventos y propiedades

### 4.1. Taxonomía de eventos

Los nombres de eventos utilizan el formato `entidad_accion`, con nombres descriptivos y verbos consistentes.

Ejemplos:

- `inbound_order_created`
- `outbound_order_created`
- `stock_threshold_triggered`
- `direct_stock_edit_rejected`
- `session_expired`
- `api_latency_recorded`

Los nombres de eventos deben mantenerse estables entre versiones siempre que sea posible.

### 4.2. Propiedades obligatorias de inventario

Los eventos de inventario deben respetar los nombres exactos establecidos por el briefing.

| Propiedad | Tipo | Regla |
|---|---|---|
| `location_id` | string | Identificador del local. |
| `country` | string | Solo `CO` o `US`. |
| `product_id` | string | Identificador del producto. |
| `product_category` | string | Categoría del producto. |
| `quantity` | number | Cantidad registrada. |
| `unit` | string | Unidad de medida del producto. |
| `currency` | string | Solo `COP` o `USD`. |
| `reason` | string | Motivo de merma cuando corresponda. |

Los campos aplicables deben incluirse en las propiedades de los eventos de inventario. No se deben sustituir los identificadores del briefing por nombres alternativos como `locationId` o `productId`.

Para `outbound_order_created` y `stock_waste_registered`, el campo `reason` utilizará exclusivamente:

- `expired`
- `kitchen_error`
- `theft_suspected`

En las salidas que no correspondan a merma, el diseño deberá distinguir el consumo normal de los registros de desperdicio. No se debe inventar un motivo de merma para una salida normal.

### 4.3. Sobre común de eventos

Todos los eventos utilizarán el siguiente sobre:

| Campo | Tipo | Descripción |
|---|---|---|
| `eventId` | string | Identificador único del evento. |
| `timestamp` | string | Fecha y hora ISO 8601 con zona horaria. |
| `sessionId` | string o null | Identificador seudónimo de sesión. |
| `userId` | string o null | Identificador seudónimo de usuario. |
| `event_type` | string | Nombre del evento según la taxonomía. |
| `schemaVersion` | string | Versión del esquema. |
| `requestId` | string o null | Identificador de correlación entre frontend, backend y logs. |
| `properties` | object | Propiedades específicas permitidas para el evento. |

Todas las claves del sobre deben existir. Los campos que admitan null deben conservar la clave aunque no exista un valor disponible.

Los identificadores de usuario y sesión deben ser seudónimos, nunca nombres ni correos electrónicos.

## 5. Catálogo de eventos

El catálogo contiene seis eventos obligatorios del briefing y dieciséis oportunidades adicionales identificadas mediante el análisis del flujo de inventario y del resto de la aplicación.

Cada evento incluye su finalidad, hipótesis, decisión habilitada y estrategia de entrega.

### 5.1. Eventos obligatorios del briefing

#### 1. `inbound_order_created`

- **Clasificación:** Obligatorio.
- **Cuándo se dispara:** Cuando un local registra la llegada de mercancía de un proveedor.
- **Qué captura:** Identificador de orden, local, país, producto, categoría, cantidad, unidad, moneda y proveedor.
- **Hipótesis:** Conocer cuánto y qué se compra, por local y proveedor, permitirá identificar oportunidades de consolidación de compras.
- **Decisión habilitada:** Consolidar compras entre locales para negociar mejores precios.
- **Entrega:** Batch. La información se utiliza para analizar compras y comparar actividad por local y proveedor. No necesita una decisión de segundos.

#### 2. `outbound_order_created`

- **Clasificación:** Obligatorio.
- **Cuándo se dispara:** Cuando un local registra consumo de ingredientes durante la preparación de platos o una salida asociada a merma.
- **Qué captura:** Identificador de orden, local, país, producto, categoría, cantidad, unidad, moneda y motivo cuando la salida corresponde a merma.
- **Hipótesis:** Conocer qué ingredientes se consumen más y a qué ritmo, por local, permitirá mejorar las sugerencias de pedidos.
- **Decisión habilitada:** Ajustar la sugerencia automática de pedidos a proveedores.
- **Entrega:** Batch. El análisis de consumo se utiliza para detectar tendencias y ajustar recomendaciones de compra, no para generar una alerta inmediata por cada salida.

#### 3. `stock_waste_registered`

- **Clasificación:** Obligatorio.
- **Cuándo se dispara:** Cuando un local registra merma por producto vencido, error de cocina o pérdida/robo.
- **Qué captura:** Identificador de orden de salida, local, país, producto, categoría, cantidad, unidad, moneda y motivo.
- **Hipótesis:** Conocer cuánto producto se pierde, por qué razón y en qué local permitirá identificar los locales con peores indicadores de merma.
- **Decisión habilitada:** Priorizar auditorías en los locales con mayor desperdicio.
- **Entrega:** Batch. La comparación de mermas por local y motivo se utiliza principalmente para análisis y priorización de auditorías.

#### 4. `stock_threshold_triggered`

- **Clasificación:** Obligatorio.
- **Cuándo se dispara:** Cuando el stock de un producto cae por debajo del mínimo configurado para ese local.
- **Qué captura:** Local, país, producto, categoría, cantidad actual, unidad y umbral configurado.
- **Hipótesis:** Conocer con qué frecuencia un local se queda corto de un ingrediente clave permitirá evaluar los umbrales y la frecuencia de reposición.
- **Decisión habilitada:** Ajustar el umbral mínimo o la frecuencia de reabastecimiento del producto.
- **Entrega:** Stream. La situación requiere visibilidad rápida para que el equipo pueda evaluar una reposición.

#### 5. `direct_stock_edit_rejected`

- **Clasificación:** Obligatorio.
- **Cuándo se dispara:** Cuando un usuario intenta modificar directamente el stock fuera de una orden y el sistema rechaza la operación.
- **Qué captura:** Local, país, producto, categoría, tipo de operación solicitada y resultado del rechazo.
- **Hipótesis:** Identificar si el personal intenta saltarse el control de trazabilidad permitirá localizar problemas de formación o permisos.
- **Decisión habilitada:** Reforzar la capacitación o revisar los permisos en los locales donde estos intentos ocurren con mayor frecuencia.
- **Entrega:** Stream. El rechazo representa una violación de una regla de negocio y debe estar disponible rápidamente para su supervisión.
- **Restricción:** No registrar el valor arbitrario que se intentó introducir ni permitir que el evento modifique el stock.

#### 6. `ingredient_price_variance_detected`

- **Clasificación:** Obligatorio.
- **Cuándo se dispara:** Cuando el coste unitario de una orden de entrada varía más de un umbral configurado respecto al histórico del mismo producto y proveedor.
- **Qué captura:** Local, país, producto, categoría, proveedor, precio anterior, precio nuevo, moneda y porcentaje de variación.
- **Hipótesis:** Identificar cuándo un ingrediente clave sube de precio de forma anómala permitirá reaccionar ante cambios relevantes de coste.
- **Decisión habilitada:** Alertar al equipo responsable para renegociar o buscar un proveedor alternativo.
- **Entrega:** Stream. Una variación significativa requiere atención operativa para poder reaccionar ante el cambio de precio.

### 5.2. Oportunidades adicionales de inventario

#### 7. `inbound_order_started`

- **Clasificación:** Oportunidad adicional.
- **Cuándo se dispara:** Cuando comienza el proceso de creación de una orden de entrada.
- **Qué captura:** Local, país, proveedor y tipo de flujo.
- **Hipótesis:** Conocer cuántas órdenes comienzan permitirá comparar inicios con órdenes completadas.
- **Decisión habilitada:** Identificar dificultades en el proceso de recepción.
- **Entrega:** Batch. Es una métrica de análisis de conversión del flujo.

#### 8. `outbound_order_started`

- **Clasificación:** Oportunidad adicional.
- **Cuándo se dispara:** Cuando comienza el proceso de creación de una orden de salida.
- **Qué captura:** Local, país, tipo de salida y origen del flujo.
- **Hipótesis:** Comparar los inicios con las órdenes completadas permitirá detectar dificultades en el registro de consumo o merma.
- **Decisión habilitada:** Mejorar el proceso de registro de salidas.
- **Entrega:** Batch. Se utiliza para análisis de comportamiento del flujo.

#### 9. `order_validation_failed`

- **Clasificación:** Oportunidad adicional.
- **Cuándo se dispara:** Cuando una orden de entrada o salida no supera una validación.
- **Qué captura:** Tipo de orden, local, país, identificador de regla de validación y categoría normalizada del error.
- **Hipótesis:** Las validaciones que más fallan pueden señalar reglas confusas o problemas de calidad de datos.
- **Decisión habilitada:** Corregir reglas, formularios o instrucciones de registro.
- **Entrega:** Stream. Los errores repetidos pueden impedir operaciones de inventario y requieren visibilidad rápida.

#### 10. `order_abandoned`

- **Clasificación:** Oportunidad adicional.
- **Cuándo se dispara:** Cuando un flujo de orden iniciado no llega a completarse dentro del criterio de abandono definido.
- **Qué captura:** Tipo de orden, local, país, etapa alcanzada y duración del flujo.
- **Hipótesis:** Los abandonos pueden revelar fricción en los procesos de entrada y salida.
- **Decisión habilitada:** Priorizar mejoras en los pasos del flujo con mayor abandono.
- **Entrega:** Batch. La medición se utiliza para análisis de conversión y tendencias.

#### 11. `inventory_search_performed`

- **Clasificación:** Oportunidad adicional.
- **Cuándo se dispara:** Cuando un usuario realiza una búsqueda en el inventario.
- **Qué captura:** Local, país, ámbito de búsqueda y cantidad de resultados.
- **Hipótesis:** Las búsquedas sin resultados o con pocos resultados pueden revelar dificultades para localizar productos.
- **Decisión habilitada:** Mejorar la organización y las herramientas de búsqueda.
- **Entrega:** Batch. Su valor principal es el análisis agregado de uso.
- **Restricción:** No registrar el texto original de búsqueda.

### 5.3. Oportunidades adicionales de autenticación y sesiones

#### 12. `login_succeeded`

- **Clasificación:** Oportunidad adicional.
- **Cuándo se dispara:** Cuando la autenticación finaliza correctamente.
- **Qué captura:** Método de autenticación y resultado.
- **Hipótesis:** Medir los accesos correctos permitirá conocer la actividad de uso y comparar intentos correctos con fallidos.
- **Decisión habilitada:** Revisar patrones de acceso y disponibilidad del sistema.
- **Entrega:** Batch. Se utiliza para análisis agregado de accesos.

#### 13. `login_failed`

- **Clasificación:** Oportunidad adicional.
- **Cuándo se dispara:** Cuando un intento de autenticación no se completa correctamente.
- **Qué captura:** Método de autenticación y categoría normalizada del fallo.
- **Hipótesis:** Los fallos repetidos pueden indicar problemas de acceso o actividad sospechosa.
- **Decisión habilitada:** Investigar patrones de fallos y mejorar las instrucciones de autenticación.
- **Entrega:** Stream. Los fallos de autenticación pueden necesitar revisión rápida.
- **Restricción:** No recopilar contraseñas, tokens ni credenciales.

#### 14. `credentials_rejected`

- **Clasificación:** Oportunidad adicional.
- **Cuándo se dispara:** Cuando el sistema rechaza las credenciales presentadas durante un intento de autenticación.
- **Qué captura:** Categoría del rechazo y método de autenticación.
- **Hipótesis:** Distinguir los rechazos de credenciales de otros fallos permitirá comprender mejor los problemas de acceso.
- **Decisión habilitada:** Revisar las causas recurrentes de rechazo y las instrucciones de acceso.
- **Entrega:** Stream. La detección rápida ayuda a identificar patrones de autenticación fallida.
- **Restricción:** Nunca recopilar el contenido de las credenciales.

#### 15. `session_expired`

- **Clasificación:** Oportunidad adicional.
- **Cuándo se dispara:** Cuando una sesión expira por las reglas de seguridad o inactividad.
- **Qué captura:** Identificador seudónimo de sesión, causa normalizada y duración de la sesión.
- **Hipótesis:** Las expiraciones frecuentes pueden interrumpir operaciones y generar fricción.
- **Decisión habilitada:** Revisar los tiempos de expiración y la experiencia de acceso.
- **Entrega:** Batch. El análisis agregado permite evaluar patrones de expiración.

#### 16. `session_ended`

- **Clasificación:** Oportunidad adicional.
- **Cuándo se dispara:** Cuando una sesión termina mediante cierre de sesión.
- **Qué captura:** Identificador seudónimo de sesión y origen del cierre.
- **Hipótesis:** Conocer cómo terminan las sesiones ayuda a comprender su duración y comportamiento.
- **Decisión habilitada:** Revisar patrones de uso y finalización de sesiones.
- **Entrega:** Batch. Es información orientada a análisis agregado.

### 5.4. Oportunidades adicionales de navegación

#### 17. `page_viewed`

- **Clasificación:** Oportunidad adicional.
- **Cuándo se dispara:** Cuando se visualiza una página identificada de la aplicación.
- **Qué captura:** Identificador permitido de página y sección de aplicación.
- **Hipótesis:** Las visitas permitirán identificar qué secciones utilizan más los operadores.
- **Decisión habilitada:** Priorizar mejoras de navegación y documentación.
- **Entrega:** Batch. Las visitas se analizan de forma agregada.
- **Restricción:** No incluir identificadores personales ni parámetros sensibles de URL.

### 5.5. Oportunidades adicionales de rendimiento y errores

#### 18. `api_latency_recorded`

- **Clasificación:** Oportunidad adicional.
- **Cuándo se dispara:** Cuando termina una solicitud a la API y se mide su duración.
- **Qué captura:** Identificador permitido del endpoint, método HTTP, código de estado y duración en milisegundos.
- **Hipótesis:** Las solicitudes lentas pueden señalar cuellos de botella en el backend.
- **Decisión habilitada:** Priorizar la optimización de endpoints con mayor latencia.
- **Entrega:** Batch. Las mediciones se utilizan para analizar tendencias de rendimiento.

#### 19. `api_request_failed`

- **Clasificación:** Oportunidad adicional.
- **Cuándo se dispara:** Cuando una solicitud a la API termina con un error.
- **Qué captura:** Identificador permitido del endpoint, código de estado y categoría normalizada del error.
- **Hipótesis:** La frecuencia y distribución de errores permiten localizar problemas técnicos recurrentes.
- **Decisión habilitada:** Priorizar investigaciones y correcciones.
- **Entrega:** Stream. Los errores que afectan a operaciones requieren visibilidad rápida.

#### 20. `frontend_error_captured`

- **Clasificación:** Oportunidad adicional.
- **Cuándo se dispara:** Cuando el frontend captura un error no gestionado o una excepción relevante.
- **Qué captura:** Categoría del error, componente o sección, identificador normalizado del error y versión de la aplicación.
- **Hipótesis:** Los errores de frontend pueden impedir que los usuarios completen operaciones aunque el backend funcione correctamente.
- **Decisión habilitada:** Priorizar correcciones de interfaz y componentes problemáticos.
- **Entrega:** Stream. Los errores que afectan a la experiencia requieren diagnóstico rápido.
- **Restricción:** No incluir datos personales, tokens, valores de formularios ni mensajes sin sanitizar.

#### 21. `page_load_completed`

- **Clasificación:** Oportunidad adicional.
- **Cuándo se dispara:** Cuando termina la carga de una página.
- **Qué captura:** Identificador permitido de página, duración de carga en milisegundos y resultado.
- **Hipótesis:** Los tiempos de carga permiten detectar secciones lentas de la aplicación.
- **Decisión habilitada:** Priorizar mejoras de rendimiento en las páginas con peores tiempos.
- **Entrega:** Batch. Las métricas de carga se analizan por página y periodo.

#### 22. `permission_denied`

- **Clasificación:** Oportunidad adicional.
- **Cuándo se dispara:** Cuando una operación es rechazada por falta de permisos.
- **Qué captura:** Identificador permitido de recurso, categoría de operación y motivo normalizado del rechazo.
- **Hipótesis:** Los rechazos frecuentes pueden indicar permisos incorrectos o dificultades de uso.
- **Decisión habilitada:** Revisar la configuración de permisos y las instrucciones operativas.
- **Entrega:** Stream. Los rechazos de autorización pueden afectar operaciones relevantes y deben ser visibles rápidamente.
- **Restricción:** No recopilar nombres ni datos personales del usuario.

## 6. Mapeo del flujo de inventario

La instrumentación debe permitir reconstruir el recorrido de una operación desde el acceso al sistema hasta su finalización o abandono.

| Etapa | Evento | Qué permite observar |
|---|---|---|
| Acceso | `login_succeeded` o `login_failed` | Resultado de autenticación. |
| Inicio de sesión de trabajo | `session_expired` o `session_ended` | Finalización o interrupción de sesión. |
| Inicio de orden | `inbound_order_started` o `outbound_order_started` | Inicio del flujo de inventario. |
| Consulta de productos | `inventory_search_performed` | Actividad de búsqueda. |
| Validación | `order_validation_failed` | Errores de validación. |
| Control de stock | `direct_stock_edit_rejected` | Intentos de evitar el flujo trazable. |
| Umbral | `stock_threshold_triggered` | Activación del mínimo configurado. |
| Finalización | `inbound_order_created` o `outbound_order_created` | Orden registrada. |
| Merma | `stock_waste_registered` | Desperdicio registrado. |
| Abandono | `order_abandoned` | Flujo que no llega a completarse. |

Los eventos deben correlacionarse mediante `sessionId`, `requestId` y los identificadores de orden cuando estén disponibles. La telemetría no debe sustituir los registros transaccionales del inventario.

## 7. Estrategia de propiedades permitidas

Cada evento tendrá una lista explícita de propiedades permitidas en `event-schemas.json`.

No se deben enviar propiedades arbitrarias. Los esquemas definen qué claves pueden emitirse, su tipo, obligatoriedad, restricciones y descripción.

Los campos del sobre común no deben duplicarse dentro de `properties`.

### 7.1. Identificadores y datos de inventario

- Usar `location_id`, `product_id` y `supplier_id` como identificadores.
- Incluir `country` con los valores `CO` o `US`.
- Incluir `product_category` según la categoría del producto.
- Conservar `quantity` y `unit`.
- Conservar `currency` como `COP` o `USD`.
- No convertir monedas ni calcular importes en una moneda distinta dentro de la telemetría.
- Incluir `reason` únicamente cuando el evento represente una merma, utilizando los valores permitidos.

### 7.2. Datos sensibles y sanitización

No se deben recopilar:

- Nombres de empleados.
- Datos de clientes.
- Correos electrónicos o teléfonos.
- Contraseñas o credenciales.
- Tokens de acceso o secretos.
- Contenido de formularios.
- Texto libre de búsquedas.
- Cuerpos completos de solicitudes o respuestas.
- Parámetros sensibles de URL.
- Mensajes de error sin sanitizar.
- Trazas que contengan información personal o secretos.

Las medidas de protección serán:

1. Utilizar identificadores seudónimos para usuario y sesión.
2. Normalizar los errores antes de emitirlos.
3. Utilizar identificadores de endpoint y página permitidos.
4. Eliminar valores sensibles antes de construir el evento.
5. Validar cada evento contra su allowlist.
6. Rechazar o eliminar propiedades desconocidas.
7. No registrar el contenido de credenciales ni valores arbitrarios enviados en operaciones rechazadas.

## 8. Estrategia de entrega

La clasificación `stream` o `batch` se basa en la urgencia de la decisión que alimenta cada evento.

### 8.1. Stream

Se propone procesamiento en tiempo real para:

- `stock_threshold_triggered`
- `direct_stock_edit_rejected`
- `order_validation_failed`
- `login_failed`
- `credentials_rejected`
- `api_request_failed`
- `frontend_error_captured`
- `permission_denied`

Justificación: estos eventos pueden afectar a la continuidad de una operación, a la seguridad o a una regla de negocio. Su visibilidad rápida permite investigar y reaccionar sin esperar a un informe periódico.

### 8.2. Batch

Se propone procesamiento por lotes para:

- `inbound_order_created`
- `outbound_order_created`
- `stock_waste_registered`
- `ingredient_price_variance_detected`
- `inbound_order_started`
- `outbound_order_started`
- `order_abandoned`
- `inventory_search_performed`
- `login_succeeded`
- `session_expired`
- `session_ended`
- `page_viewed`
- `api_latency_recorded`
- `page_load_completed`

Justificación: estos eventos alimentan principalmente análisis históricos, comparaciones por local, tendencias de consumo, seguimiento de procesos y reportes de rendimiento.

La clasificación es una propuesta de diseño para el futuro pipeline de telemetría. No implica que la infraestructura esté implementada.

## 9. Throttling y debouncing

Se propone:

- Aplicar debouncing a eventos `page_viewed` repetidos cuando se produzcan por navegación rápida dentro de una misma página.
- Aplicar throttling a eventos repetidos `stock_threshold_triggered` para el mismo producto y local mientras persista la misma condición de umbral.
- Agrupar mediciones de rendimiento de alto volumen cuando el análisis no requiera cada muestra individual.
- Limitar eventos técnicos repetitivos sin perder información sobre la frecuencia y gravedad de los errores.
- No descartar órdenes reales, registros de merma ni rechazos de modificación directa del stock.
- No agrupar transacciones distintas de forma que se pierda su trazabilidad.

Los intervalos y límites concretos deberán configurarse y validarse durante la implementación. Este plan no inventa ventanas temporales definitivas.

## 10. Riesgos y exclusiones

### 10.1. Exclusiones

- No se instrumentarán modificaciones directas exitosas del stock porque esa operación no está permitida.
- No se recopilarán datos personales de empleados ni clientes.
- No se recopilarán credenciales ni secretos.
- No se enviarán cuerpos completos de solicitudes o respuestas.
- No se recopilarán textos libres de búsqueda o formularios.
- No se convertirán monedas en la capa de telemetría.
- No se sustituirán los registros transaccionales por eventos de telemetría.

### 10.2. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Eventos duplicados | Identificador único `eventId` y controles de deduplicación. |
| Pérdida de correlación | Utilizar `sessionId`, `requestId` e identificadores de orden cuando estén disponibles. |
| Exposición de datos sensibles | Allowlist, seudonimización y sanitización antes del envío. |
| Exceso de volumen | Throttling, debouncing y agregación controlada. |
| Alertas retrasadas | Stream para eventos que requieren atención rápida. |
| Formatos inconsistentes | Validación contra esquemas versionados. |
| Monedas mezcladas | Conservar la moneda local `COP` o `USD`, sin conversión. |
| Pérdida de trazabilidad | Mantener el flujo obligatorio de órdenes de entrada y salida. |
| Eventos sin utilidad | Exigir hipótesis y decisión concreta para cada evento. |

## 11. Versionado y validación

- Todos los eventos deben incluir el sobre común.
- `timestamp` debe respetar ISO 8601 con zona horaria.
- `event_type` debe coincidir con un nombre del catálogo.
- `schemaVersion` identifica la versión del esquema.
- Las propiedades deben cumplir el allowlist de cada evento.
- Los campos obligatorios deben validarse antes de aceptar un evento.
- Los campos de país, moneda y motivo deben respetar los valores permitidos.
- Los campos del sobre común no deben repetirse en `properties`.
- Los cambios incompatibles deben generar una nueva versión de esquema.
- `event-schemas.json` debe reflejar exactamente el catálogo y las propiedades descritas aquí.

## 12. Criterios de aceptación

El diseño estará listo para implementación cuando:

1. Incluya los seis eventos obligatorios del briefing.
2. Incluya oportunidades adicionales de negocio y de salud técnica.
3. Cubra autenticación, navegación, rendimiento, errores e inventario.
4. Permita observar al menos cinco puntos del flujo de inventario.
5. Cada evento tenga descripción, hipótesis, decisión y estrategia de entrega.
6. El sobre común esté definido y sea consistente.
7. Los eventos de inventario utilicen los nombres exactos de propiedades del briefing.
8. Las propiedades tengan tipo, obligatoriedad, descripción y restricciones.
9. Los datos sensibles estén identificados y tengan reglas de sanitización.
10. La entrega stream/batch esté justificada según la urgencia operativa.
11. Existan reglas de throttling, debouncing, riesgos y exclusiones.
12. El JSON sea válido y coincida con este documento.
13. Otro desarrollador pueda instrumentar los eventos sin necesitar aclaraciones adicionales.
