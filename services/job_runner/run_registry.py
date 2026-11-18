"""Registro y control de trabajos nocturnos de Brasaland."""

from datetime import date

from sqlalchemy import text

from services.job_runner.database import get_engine


JOB_NAME = "brasaland-nightly-export"


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
    """Comprueba si existe una ejecucion nocturna activa."""
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
    """Crea un trabajo pendiente si todavia no existe para esa fecha."""
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
    """Intenta adquirir el bloqueo y comenzar el trabajo."""
    from uuid import UUID

    from sqlalchemy.exc import IntegrityError

    engine = get_engine()

    try:
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
        except IntegrityError:
            # Otro trabajo ya tiene el estado processing.
            return False
    finally:
        engine.dispose()


def finish_job_run(
    run_id: str,
    status: str,
    error_message: str | None = None,
    csv_path: str | None = None,
) -> None:
    """Finaliza un trabajo activo y libera su bloqueo."""
    from uuid import UUID

    if status not in ("completed", "failed"):
        raise ValueError("El estado final debe ser completed o failed.")

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
