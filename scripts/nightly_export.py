
"""Exportacion nocturna de telemetria y ejecucion del pipeline."""

import csv
import logging
import os
import subprocess
import sys
import tempfile

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import text

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.job_runner.database import get_engine
from services.job_runner.run_registry import (
    JOB_NAME,
    create_job_run,
    finish_job_run,
    has_completed_for_date,
    job_execution_lock,
    recover_abandoned_job_runs,
    start_job_run,
)


RAW_DIR = REPO_ROOT / "data" / "raw"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s job=nightly_export %(message)s",
)
logger = logging.getLogger(__name__)


def get_target_date() -> date:
    """Usa TARGET_DATE o, por defecto, el dia anterior en UTC."""
    configured_date = os.getenv("TARGET_DATE")

    if configured_date:
        return date.fromisoformat(configured_date)

    return datetime.now(timezone.utc).date() - timedelta(days=1)


def get_week_start(target_date: date) -> date:
    """Devuelve el lunes de la semana correspondiente."""
    return target_date - timedelta(days=target_date.weekday())


def export_telemetry_csv(target_date: date) -> Path:
    """Exporta un respaldo completo sin sobrescribir CSV existentes."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = RAW_DIR / f"telemetry_{target_date.isoformat()}.csv"

    if csv_path.exists():
        logger.info(
            "status=processing CSV existente: %s",
            csv_path.name,
        )
        return csv_path

    temporary_path = None
    engine = get_engine()

    try:
        with engine.connect() as connection:
            result = connection.execute(
                text("""
                    SELECT *
                    FROM public.telemetry_events
                    WHERE timestamp >= :start_date
                      AND timestamp < :end_date
                    ORDER BY timestamp
                """),
                {
                    "start_date": datetime.combine(
                        target_date,
                        datetime.min.time(),
                        tzinfo=timezone.utc,
                    ),
                    "end_date": datetime.combine(
                        target_date + timedelta(days=1),
                        datetime.min.time(),
                        tzinfo=timezone.utc,
                    ),
                },
            )

            with tempfile.NamedTemporaryFile(
                mode="w",
                newline="",
                encoding="utf-8",
                dir=RAW_DIR,
                prefix=".telemetry_",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                writer = csv.writer(temporary_file)
                writer.writerow(result.keys())
                writer.writerows(result)

        if csv_path.exists():
            logger.info(
                "status=processing CSV existente: %s",
                csv_path.name,
            )
            return csv_path

        try:
            os.link(temporary_path, csv_path)
        except FileExistsError:
            logger.info(
                "status=processing CSV creado por otro proceso: %s",
                csv_path.name,
            )

        logger.info(
            "status=processing CSV disponible: %s",
            csv_path.name,
        )
        return csv_path

    finally:
        engine.dispose()

        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def run_pipeline(target_date: date) -> None:
    """Ejecuta el pipeline semanal como subproceso independiente."""
    week_start = get_week_start(target_date)

    command = [
        sys.executable,
        str(REPO_ROOT / "data" / "pipelines" / "pipeline.py"),
        "--week-start",
        week_start.isoformat(),
    ]

    logger.info(
        "status=processing Iniciando pipeline: week_start=%s",
        week_start,
    )

    subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=True,
    )

    logger.info(
        "status=processing Pipeline finalizado: week_start=%s",
        week_start,
    )


def main() -> None:
    """Coordina el trabajo nocturno con bloqueo de PostgreSQL."""
    run_id = None
    started = False

    try:
        with job_execution_lock() as acquired:

            if not acquired:
                logger.info(
                    "status=processing Otra instancia mantiene el bloqueo; "
                    "se cancela la ejecucion."
                )
                return

            recovered = recover_abandoned_job_runs()

            if recovered:
                logger.warning(
                    "status=failed Se recuperaron %s trabajos abandonados.",
                    recovered,
                )

            target_date = get_target_date()

            if has_completed_for_date(target_date):
                logger.info(
                    "status=completed Trabajo ya realizado; se omite: date=%s",
                    target_date,
                )
                return

            run_id = create_job_run(target_date)

            if run_id is None:
                engine = get_engine()

                try:
                    with engine.connect() as connection:
                        run_id = str(
                            connection.execute(
                                text("""
                                    SELECT id
                                    FROM reporting.job_runs
                                    WHERE job_name = :job_name
                                      AND target_date = :target_date
                                """),
                                {
                                    "job_name": JOB_NAME,
                                    "target_date": target_date,
                                },
                            ).scalar_one()
                        )
                finally:
                    engine.dispose()

            if not start_job_run(run_id):
                logger.info(
                    "status=processing No se pudo iniciar el trabajo: date=%s",
                    target_date,
                )
                return

            started = True

            logger.info(
                "status=processing Trabajo iniciado: run_id=%s date=%s",
                run_id,
                target_date,
            )

            try:
                csv_path = export_telemetry_csv(target_date)
                run_pipeline(target_date)

                finish_job_run(
                    run_id,
                    status="completed",
                    csv_path=str(csv_path),
                )

                started = False

                logger.info(
                    "status=completed Trabajo finalizado: run_id=%s",
                    run_id,
                )

            except Exception as exc:
                logger.exception(
                    "status=failed Error del trabajo nocturno: run_id=%s",
                    run_id,
                )

                if started:
                    try:
                        finish_job_run(
                            run_id,
                            status="failed",
                            error_message=(
                                f"{type(exc).__name__}: {exc}"
                            )[:1000],
                        )
                        started = False

                    except Exception:
                        logger.exception(
                            "status=failed No se pudo registrar el fallo: "
                            "run_id=%s",
                            run_id,
                        )

                raise

    except Exception:
        if not started:
            logger.exception(
                "status=failed Error al preparar o coordinar el trabajo."
            )
        raise


if __name__ == "__main__":
    main()
