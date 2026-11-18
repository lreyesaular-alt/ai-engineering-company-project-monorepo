# Trabajo nocturno de telemetría de Brasaland

## Objetivo

Ejecutar diariamente, de forma independiente de FastAPI, un respaldo CSV de public.telemetry_events y lanzar el pipeline semanal existente.

## Componentes

- scripts/nightly_export.py: controlador principal.
- services/job_runner/run_registry.py: estados y bloqueo de ejecuciones.
- services/job_runner/database.py: conexión a PostgreSQL.
- data/migrations/001_create_job_runs.sql: tabla reporting.job_runs.
- services/job_runner/nightly-export.cron: programación nocturna.

## Fecha y exportación

Por defecto, el trabajo procesa el día anterior en UTC. La variable de entorno TARGET_DATE permite seleccionar una fecha con formato AAAA-MM-DD.

El respaldo se guarda en data/raw/telemetry_AAAA-MM-DD.csv.

El CSV incluye todas las columnas de public.telemetry_events correspondientes al día UTC seleccionado. Los archivos existentes no se sobrescriben.

El CSV es un respaldo, no la entrada del pipeline.

## Ejecución manual

Desde la raíz del repositorio, con el entorno virtual activado y la conexión a PostgreSQL configurada, ejecutar:

    python -m scripts.nightly_export

Para procesar una fecha concreta desde PowerShell:

    $env:TARGET_DATE = '2026-11-17'
    python -m scripts.nightly_export
    Remove-Item Env:TARGET_DATE

IMPORTANTE: estos comandos ejecutan el trabajo real, incluida la exportación CSV y el pipeline semanal. No son pruebas simuladas.

## Estados y reintentos

Los trabajos se registran en reporting.job_runs con cuatro estados:

- pending: trabajo creado, todavía sin iniciar.
- processing: trabajo en ejecución.
- completed: exportación y pipeline finalizados correctamente.
- failed: trabajo terminado con error.

Si una fecha ya está completed, no se vuelve a procesar. Si está failed, puede reintentarse.

Un índice único parcial de PostgreSQL impide dos ejecuciones simultáneas del mismo trabajo.

IMPORTANTE: si el proceso se interrumpe bruscamente, puede quedar en processing. Antes de liberar ese bloqueo manualmente, hay que comprobar que no exista ningún proceso activo.

## Programación nocturna con cron

El archivo services/job_runner/nightly-export.cron programa la ejecución diaria a las 02:00 UTC.

Expresión cron: 0 2 * * *

El comando utiliza python -m scripts.nightly_export y se ejecuta independientemente de FastAPI.

Antes de instalarlo en Linux, sustituir /opt/brasaland por la ruta real del repositorio, verificar el entorno virtual, los permisos, la conexión a PostgreSQL y la zona horaria del servicio cron.

Para instalar la configuración, después de revisarla:

    crontab services/job_runner/nightly-export.cron

IMPORTANTE: el archivo cron todavía no está instalado ni activo. La instalación debe realizarse en el entorno Linux de despliegue.

## Logs y recuperación ante fallos

Los logs incluyen fecha, hora, nivel, nombre del trabajo y estado. Los errores se registran con nivel ERROR.

Si el trabajo falla:

1. Revisar los logs del proceso nocturno.
2. Consultar reporting.job_runs para identificar la fecha y el error.
3. Comprobar que no exista otra ejecución activa.
4. Corregir la causa del fallo.
5. Reintentar con TARGET_DATE si el estado es failed.

Si el proceso termina inesperadamente y queda en processing, no modificar ese estado sin comprobar primero que el proceso original haya terminado.

## Seguridad

No incluir credenciales, archivos .env ni datos sensibles en logs, documentación o Pull Requests.
