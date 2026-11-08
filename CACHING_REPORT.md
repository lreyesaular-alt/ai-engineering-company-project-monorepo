# Informe técnico de optimización de caché y rendimiento

## 1. Objetivo del proyecto

El objetivo es mejorar el rendimiento de la aplicación mediante técnicas de almacenamiento en caché en el backend y optimización de carga y procesamiento en el frontend.

Se han implementado dos mecanismos de caché, un middleware de medición de tiempos, carga diferida de componentes y memorización de cálculos.

## 2. Análisis y optimización del backend

### 2.1. Middleware de medición

Se ha implementado un middleware en `services/api/main.py` que:

- Mide el tiempo de procesamiento de cada solicitud.
- Registra el método HTTP, la ruta y la duración en los logs.
- Añade la cabecera `X-Process-Time` a la respuesta.

Esto permite observar el comportamiento de la API y comparar los tiempos de respuesta.

### 2.2. Selección de endpoints para caché

Se han seleccionado dos endpoints:

**Endpoint `/api/incidents/summary`**

Devuelve información agregada sobre las incidencias, como su distribución por categoría y estado.

Se ha seleccionado porque sus resultados se obtienen a partir de consultas a la base de datos y pueden reutilizarse durante un periodo breve sin consultar repetidamente los mismos datos.

**Endpoint `/inventory/products`**

Devuelve el listado de productos del inventario.

Se ha seleccionado porque permite reutilizar resultados entre solicitudes y reducir consultas repetidas a la base de datos.

No se han cacheado los endpoints de pedidos específicos de usuarios, para evitar almacenar respuestas personalizadas en una caché compartida.

### 2.3. Estrategia de caché y TTL

Ambos endpoints utilizan una caché en memoria con un TTL de 60 segundos.

Se ha elegido este periodo como equilibrio entre rendimiento y actualización de los datos:

- Un TTL demasiado corto reduciría las posibilidades de reutilizar la caché.
- Un TTL demasiado largo podría mostrar información desactualizada durante más tiempo.
- Los 60 segundos permiten reducir consultas repetidas manteniendo una ventana limitada de antigüedad de los datos.

### 2.4. Invalidación de caché

En el inventario, la caché se invalida después de:

- Crear un producto.
- Registrar una entrada de inventario.
- Registrar una salida de inventario.

Para el resumen de incidencias existe una función de invalidación, pero no está conectada a operaciones de escritura.

El endpoint `/api/incidents/analyze` únicamente valida y analiza archivos CSV. No modifica la base de datos. Durante la revisión no se identificaron endpoints de creación, actualización o eliminación de incidencias.

Por tanto, la invalidación automática del resumen cuando cambian las incidencias queda como una limitación pendiente.

## 3. Optimización del frontend

### 3.1. Lazy Loading

Se ha utilizado `next/dynamic` para separar dos componentes:

**IncidentStats**

Muestra estadísticas de incidencias por categoría y estado en el dashboard.

Se ha separado del componente principal para dividir el código y evitar incluir toda su implementación en el módulo inicial del dashboard.

**IncidentStatusControls**

Contiene los botones para cambiar el estado de una incidencia.

Se utiliza en la página de detalle, por lo que se ha separado del resto de la interfaz para reducir el código asociado a otras páginas.

Ambos componentes disponen de mensajes de carga mientras se prepara su módulo.

La implementación permite división de código mediante módulos independientes. No se ha realizado una medición específica del tamaño de los paquetes ni del tiempo de descarga de estos módulos.

### 3.2. Memorización con useMemo

En `app/incidents/page.tsx` se utiliza `useMemo` para memorizar el resultado del filtrado de incidencias.

El cálculo aplica dos criterios:

- Categoría de la incidencia.
- Estado de la incidencia.

Las dependencias son `incidents`, `category` y `status`.

De esta manera, el filtrado no se vuelve a calcular cuando se producen renderizados que no modifican ninguno de esos valores.

## 4. Datos de prueba y mediciones

Se han cargado 96 incidencias en la base de datos para realizar las pruebas.

### 4.1. Resumen de incidencias sin caché

| Solicitud | Tiempo |
|---|---:|
| 1 | 280,03 ms |
| 2 | 285,42 ms |
| 3 | 361,28 ms |
| 4 | 280,44 ms |
| 5 | 249,45 ms |
| **Media** | **291,32 ms** |

### 4.2. Resumen de incidencias con caché

Se excluye la primera solicitud fría, que registró 2.913,19 ms debido al coste de conexión inicial.

| Solicitud | Tiempo |
|---|---:|
| 1 | 0,95 ms |
| 2 | 0,93 ms |
| 3 | 0,81 ms |
| 4 | 0,78 ms |
| **Media** | **0,87 ms** |

La reducción media observada es aproximadamente del 99,70 % respecto a la referencia sin caché.

### 4.3. Inventario de productos

| Medición | Tiempo |
|---|---:|
| Primera solicitud (MISS) | 1.390,07 ms |
| Solicitud con caché 1 | 1,79 ms |
| Solicitud con caché 2 | 1,05 ms |
| Solicitud con caché 3 | 1,18 ms |
| Solicitud con caché 4 | 1,15 ms |
| **Media con caché** | **1,29 ms** |
| Solicitud tras expirar el TTL | 163,02 ms |

Se observa una respuesta rápida cuando los datos están disponibles en caché y una nueva consulta cuando expira el TTL.

No se dispone de una medición equivalente sin caché para este endpoint, por lo que no se calcula un porcentaje de mejora.

### 4.4. Limitaciones de las mediciones

Las mediciones se realizaron mediante solicitudes manuales. No se dispone de una prueba de carga concurrente ni de una comparación de rendimiento con diferentes volúmenes de datos.

El conjunto de prueba utilizado contiene 96 incidencias.

## 5. Pruebas y validación

### Backend

Se ejecutó la suite de pruebas con:

```powershell
$env:PYTHONPATH = (Get-Location).Path
pytest
```

Resultado:

- 43 pruebas ejecutadas.
- 43 pruebas superadas.
- Tiempo: 7,57 segundos.

### Frontend

- `npx tsc --noEmit`: correcto.
- `npm run build`: compilación correcta.
- `npm run lint`: cero errores y tres advertencias.

Las advertencias corresponden a variables no utilizadas y a una recomendación de navegación interna de Next.js.

## 6. Limitaciones de la implementación

- Las cachés son locales al proceso y no se comparten entre varios trabajadores.
- El TTL de ambas cachés es de 60 segundos.
- La invalidación del inventario está conectada a las operaciones de modificación correspondientes.
- La invalidación del resumen de incidencias no está conectada a operaciones de escritura, porque no se identificaron rutas que modifiquen incidencias.
- No se ha realizado una medición específica del tamaño de los paquetes del frontend.
- No se han realizado pruebas de carga concurrente.
- No se dispone de una comparación sin caché para el endpoint de inventario.

## 7. Conclusión

La implementación ha permitido reducir significativamente el tiempo de respuesta del resumen de incidencias cuando se reutilizan resultados almacenados en caché.

También se han incorporado mecanismos de caché para el inventario, carga diferida de dos componentes del frontend y memorización del filtrado de incidencias mediante `useMemo`.

Las pruebas del backend han finalizado con 43 resultados satisfactorios y el frontend compila correctamente.

El informe recoge las mediciones realizadas, las decisiones técnicas y las limitaciones detectadas durante el desarrollo.

