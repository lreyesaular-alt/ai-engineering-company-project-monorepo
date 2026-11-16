"""Registro de ejecuciones del pipeline de Brasaland."""

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from dotenv import dotenv_values
from sqlalchemy import create_engine, text


def get_engine():
    """Crea una conexion configurada sin mostrar credenciales."""
    repo_root = Path(__file__).resolve().parents[2]
    env_path = repo_root / "services" / "api" / ".env"
    database_url = dotenv_values(env_path).get("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL no esta configurada.")

    return create_engine(
        database_url,
        echo=False,
        connect_args={"connect_timeout": 10},
    )


def start_pipeline_run(week_start: date) -> str:
    """Registra el inicio y devuelve el identificador de ejecucion."""
    engine = get_engine()

    try:
        with engine.begin() as connection:
            run_id = connection.execute(
                text("""
                    INSERT INTO reporting.pipeline_runs (
                        pipeline_name, week_start, status
                    )
                    VALUES (
                        'brasaland-weekly-performance',
                        :week_start,
                        'running'
                    )
                    RETURNING id
                """),
                {"week_start": week_start},
            ).scalar_one()

        return str(run_id)
    finally:
        engine.dispose()


def finish_pipeline_run(
    run_id: str,
    status: str,
    rows_processed: int = 0,
    error_message: str | None = None,
) -> None:
    """Marca una ejecucion como completada o fallida."""
    if status not in ("completed", "failed"):
        raise ValueError("Estado final invalido.")

    engine = get_engine()

    try:
        with engine.begin() as connection:
            result = connection.execute(
                text("""
                    UPDATE reporting.pipeline_runs
                    SET status = :status,
                        finished_at = NOW(),
                        rows_processed = :rows_processed,
                        error_message = :error_message
                    WHERE id = :run_id
                      AND status = 'running'
                """),
                {
                    "run_id": UUID(run_id),
                    "status": status,
                    "rows_processed": rows_processed,
                    "error_message": error_message,
                },
            )

            if result.rowcount != 1:
                raise RuntimeError(
                    "No se encontro una ejecucion activa para finalizar."
                )
    finally:
        engine.dispose()


def get_latest_pipeline_run() -> dict | None:
    """Devuelve la ultima ejecucion registrada."""
    engine = get_engine()

    try:
        with engine.connect() as connection:
            record = connection.execute(
                text("""
                    SELECT
                        id,
                        pipeline_name,
                        week_start,
                        status,
                        started_at,
                        finished_at,
                        rows_processed,
                        error_message
                    FROM reporting.pipeline_runs
                    ORDER BY started_at DESC, id DESC
                    LIMIT 1
                """)
            ).mappings().first()

        if record is None:
            return None

        return {
            key: (
                str(value)
                if isinstance(value, UUID)
                else value.isoformat()
                if isinstance(value, (date, datetime))
                else int(value)
                if isinstance(value, Decimal)
                else value
            )
            for key, value in dict(record).items()
        }
    finally:
        engine.dispose()
