
"""Registro y control de trabajos nocturnos de Brasaland."""

from contextlib import contextmanager
from datetime import date
from uuid import UUID

from sqlalchemy import text

from services.job_runner.database import get_engine


JOB_NAME = "nightly_export"

# Identificador estable y exclusivo para el bloqueo de este trabajo.
# PostgreSQL utiliza un advisory lock de sesión.
ADVISORY_LOCK_KEY = 7319052026


@contextmanager
def job_execution_lock():
    """
    Mantiene un advisory lock de PostgreSQL durante toda la ejecución.

    Si el proceso termina abruptamente, PostgreSQL libera el bloqueo
    cuando detecta que la conexión de sesión se ha cerrado.
    """
    engine = get_engine()
    connection = None
    acquired = False

    try:
        connection = engine.connect()

        acquired = bool(
            connection.execute(
                text("SELECT pg_try_advisory_lock(:lock_key)"),
                {"lock_key": ADVISORY_LOCK_KEY},
            ).scalar_one()
        )

        # El advisory lock es de sesión: el commit no lo libera.
        connection.commit()

        yield acquired

    finally:
        if connection is not None:
            if acquired:
                try:
                    connection.execute(
                        text("SELECT pg_advisory_unlock(:lock_key)"),
                        {"lock_key": ADVISORY_LOCK_KEY},
                    )
                    connection.commit()
                except Exception:
                    # Evita devolver al pool una conexión cuyo estado
                    # de bloqueo no podemos garantizar.
                    connection.invalidate()

            connection.close()

        engine.dispose()


def recover_abandoned_job_runs() -> int:
    """
    Marca como failed los trabajos processing abandonados.

    IMPORTANTE: debe llamarse únicamente después de adquirir
    job_execution_lock(), que garantiza que no existe otro ejecutor
    cooperativo activo del nightly_export.
    """
    engine = get_engine()

    try:
        with engine.begin() as connection:
            result = connection.execute(
                text("""
                    UPDATE reporting.job_runs
                    SET status = 'failed',
                        finished_at = NOW(),
                        error_message = :error_message
                    WHERE job_name = :job_name
                      AND status = 'processing'
                """),
                {
                    "job_name": JOB_NAME,
                    "error_message": (
                        "Ejecucion abandonada: el proceso anterior "
                        "termino sin registrar su estado final."
                    ),
                },
            )

            return result.rowcount
    finally:
        engine.dispose()


def has_completed_for_date(target_date: date) -> bool:
    """Comprueba si el trabajo ya finalizo para la fecha indicada."""
    engine = get_engine()

    try:
        with engine.connect() as connection:
            result = connection.execute(
                text("""
                    SELECT EXISTS (
                        SELECT 1
                        FROM reporting.job_runs
                        WHERE job_name = :job_name
                          AND target_date = :target_date
                          AND status = 'completed'
                    )
                """),
                {
                    "job_name": JOB_NAME,
                    "target_date": target_date,
                },
            ).scalar_one()

        return bool(result)
    finally:
        engine.dispose()


def has_processing_lock() -> bool:
    """Comprueba si existe un trabajo registrado como processing."""
    engine = get_engine()

    try:
        with engine.connect() as connection:
            result = connection.execute(
                text("""
                    SELECT EXISTS (
                        SELECT 1
                        FROM reporting.job_runs
                        WHERE job_name = :job_name
                          AND status = 'processing'
                    )
                """),
                {"job_name": JOB_NAME},
            ).scalar_one()

        return bool(result)
    finally:
        engine.dispose()


def create_job_run(target_date: date) -> str | None:
    """Crea un trabajo pendiente si todavía no existe para esa fecha."""
    engine = get_engine()

    try:
        with engine.begin() as connection:
            run_id = connection.execute(
                text("""
                    INSERT INTO reporting.job_runs (
                        job_name, target_date, status
                    )
                    VALUES (
                        :job_name, :target_date, 'pending'
                    )
                    ON CONFLICT (job_name, target_date) DO NOTHING
                    RETURNING id
                """),
                {
                    "job_name": JOB_NAME,
                    "target_date": target_date,
                },
            ).scalar_one_or_none()

        return str(run_id) if run_id is not None else None
    finally:
        engine.dispose()


def start_job_run(run_id: str) -> bool:
    """Intenta comenzar un trabajo pendiente o fallido."""
    engine = get_engine()

    try:
        with engine.begin() as connection:
            result = connection.execute(
                text("""
                    UPDATE reporting.job_runs
                    SET status = 'processing',
                        started_at = NOW(),
                        finished_at = NULL,
                        error_message = NULL
                    WHERE id = :run_id
                      AND status IN ('pending', 'failed')
                """),
                {"run_id": UUID(run_id)},
            )

            return result.rowcount == 1
    finally:
        engine.dispose()


def finish_job_run(
    run_id: str,
    status: str,
    error_message: str | None = None,
    csv_path: str | None = None,
) -> None:
    """Finaliza un trabajo activo y registra su resultado."""
    if status not in ("completed", "failed"):
        raise ValueError(
            "El estado final debe ser completed o failed."
        )

    engine = get_engine()

    try:
        with engine.begin() as connection:
            result = connection.execute(
                text("""
                    UPDATE reporting.job_runs
                    SET status = :status,
                        finished_at = NOW(),
                        error_message = :error_message,
                        csv_path = COALESCE(:csv_path, csv_path)
                    WHERE id = :run_id
                      AND status = 'processing'
                """),
                {
                    "run_id": UUID(run_id),
                    "status": status,
                    "error_message": error_message,
                    "csv_path": csv_path,
                },
            )

            if result.rowcount != 1:
                raise RuntimeError(
                    "No se encontro un trabajo activo para finalizar."
                )
    finally:
        engine.dispose()
