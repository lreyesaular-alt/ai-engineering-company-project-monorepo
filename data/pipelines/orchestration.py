"""Orquestacion del pipeline semanal desde la API."""

from datetime import date


def trigger_weekly_location_performance_flow(week_start: date) -> dict:
    """Ejecuta el pipeline de Prefect y devuelve su resultado."""
    if week_start.weekday() != 0:
        raise ValueError("week_start debe corresponder a un lunes.")

    from data.pipelines.pipeline import weekly_performance_flow

    rows_processed = weekly_performance_flow(week_start.isoformat())

    return {
        "pipeline_name": "brasaland-weekly-performance",
        "week_start": week_start.isoformat(),
        "status": "completed",
        "rows_processed": rows_processed,
    }
