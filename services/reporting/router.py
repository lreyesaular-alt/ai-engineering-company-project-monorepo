"""Endpoints independientes de reporting de Brasaland."""

from datetime import date

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/reporting", tags=["reporting"])


@router.get("/weekly-location-performance")
def weekly_location_performance(week_start: date):
    """Consulta el reporte semanal por ubicacion."""
    if week_start.weekday() != 0:
        raise HTTPException(
            status_code=422,
            detail="week_start debe corresponder a un lunes.",
        )

    from data.pipelines.reporting_queries import (
        get_weekly_location_performance,
    )

    return {
        "week_start": week_start.isoformat(),
        "locations": get_weekly_location_performance(week_start),
    }


@router.get("/pipeline-runs/latest")
def latest_pipeline_run():
    """Consulta la ejecucion mas reciente del pipeline."""
    from data.pipelines.run_registry import get_latest_pipeline_run

    run = get_latest_pipeline_run()

    if run is None:
        raise HTTPException(
            status_code=404,
            detail="No existen ejecuciones registradas.",
        )

    return run


@router.post("/pipeline-runs")
def trigger_pipeline_run(week_start: date):
    """Ejecuta el pipeline semanal mediante Prefect."""
    if week_start.weekday() != 0:
        raise HTTPException(
            status_code=422,
            detail="week_start debe corresponder a un lunes.",
        )

    from data.pipelines.orchestration import (
        trigger_weekly_location_performance_flow,
    )

    try:
        return trigger_weekly_location_performance_flow(week_start)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="El pipeline fallo. Consulte /reporting/pipeline-runs/latest.",
        ) from None
