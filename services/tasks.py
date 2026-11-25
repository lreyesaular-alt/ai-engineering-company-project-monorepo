
import logging
import time
from pathlib import Path

from services.celery_app import celery_app
from services.dlq import DLQTask
from services.api.incident_analysis import analyze_csv

logger = logging.getLogger(__name__)


# ============================================================
# LIMPIEZA DE ARCHIVOS CSV TEMPORALES
# ============================================================

class CSVTask(DLQTask):
    """
    Limpia el CSV cuando la tarea termina definitivamente.

    SUCCESS: elimina el archivo.
    FAILURE: elimina el archivo.
    RETRY: conserva el archivo para el siguiente intento.
    """

    abstract = True

    def after_return(
        self,
        status,
        retval,
        task_id,
        args,
        kwargs,
        einfo,
    ):
        try:
            if status in ("SUCCESS", "FAILURE") and args:
                file_path = Path(args[0])

                file_path.unlink(missing_ok=True)

                logger.info(
                    "task_id=%s state=%s CSV temporal eliminado: %s",
                    task_id,
                    status,
                    file_path,
                )

        except Exception:
            logger.exception(
                "No se pudo limpiar el CSV de task_id=%s",
                task_id,
            )

        finally:
            super().after_return(
                status,
                retval,
                task_id,
                args,
                kwargs,
                einfo,
            )


# ============================================================
# TAREA DE PRUEBA ASINCRONA
# ============================================================

@celery_app.task(
    bind=True,
    base=DLQTask,
    name="brasaland.test_async_task",
    max_retries=3,
    autoretry_for=(ValueError,),
    retry_backoff=2,
    retry_backoff_max=60,
    retry_jitter=False,
)
def test_async_task(self, seconds: int = 5):
    start = time.monotonic()
    task_id = self.request.id
    attempt = self.request.retries + 1

    logger.info(
        "task_id=%s attempt=%s state=STARTED",
        task_id,
        attempt,
    )

    try:
        if seconds < 0:
            raise ValueError(
                "Fallo controlado para probar los reintentos"
            )

        time.sleep(seconds)

        result = {
            "message": "Tarea completada correctamente",
            "seconds": seconds,
        }

        logger.info(
            "task_id=%s attempt=%s state=SUCCESS duration=%.2fs",
            task_id,
            attempt,
            time.monotonic() - start,
        )

        return result

    except Exception:
        logger.exception(
            "task_id=%s attempt=%s state=ERROR duration=%.2fs",
            task_id,
            attempt,
            time.monotonic() - start,
        )
        raise


# ============================================================
# ANALISIS ASINCRONO DE INCIDENTES CSV
# ============================================================

@celery_app.task(
    bind=True,
    base=CSVTask,
    name="brasaland.analyze_incidents_csv",
    max_retries=3,
    autoretry_for=(OSError,),
    retry_backoff=2,
    retry_backoff_max=60,
    retry_jitter=False,
)
def analyze_incidents_csv_task(self, file_path: str):
    start = time.monotonic()
    task_id = self.request.id
    attempt = self.request.retries + 1

    logger.info(
        "task_id=%s attempt=%s state=STARTED",
        task_id,
        attempt,
    )

    try:
        # Redis recibe únicamente la ruta del archivo.
        # El procesamiento ocurre en el worker Celery.
        contents = Path(file_path).read_bytes()

        result = analyze_csv(contents)

        logger.info(
            "task_id=%s attempt=%s state=SUCCESS duration=%.2fs",
            task_id,
            attempt,
            time.monotonic() - start,
        )

        return result

    except Exception:
        logger.exception(
            "task_id=%s attempt=%s state=ERROR duration=%.2fs",
            task_id,
            attempt,
            time.monotonic() - start,
        )
        raise
