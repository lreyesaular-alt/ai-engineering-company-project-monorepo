
import logging
import traceback

from celery import Task
from sqlmodel import Session

from services.api.database import engine
from services.api.dlq_models import DeadLetterTask

logger = logging.getLogger(__name__)


class DLQTask(Task):
    """Registra en la base de datos los fallos definitivos de Celery."""

    abstract = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        retry_count = self.request.retries

        error_traceback = (
            einfo.traceback
            if einfo is not None
            else "".join(
                traceback.format_exception(
                    type(exc), exc, exc.__traceback__
                )
            )
        )

        try:
            with Session(engine) as session:
                record = DeadLetterTask(
                    task_id=task_id,
                    task_name=self.name,
                    retry_count=retry_count,
                    error=error_traceback,
                )
                session.add(record)
                session.commit()

            logger.error(
                "DLQ task_id=%s retries=%s state=FAILURE",
                task_id,
                retry_count,
            )

        except Exception:
            logger.exception(
                "No se pudo guardar en DLQ task_id=%s",
                task_id,
            )

        super().on_failure(exc, task_id, args, kwargs, einfo)
