
from io import BytesIO

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlmodel import Session, select

from services.api.auth.profiles_routes import router as profiles_router
from services.api.auth.routes import router as auth_router
from services.api.auth.users_routes import router as users_router
from services.api.database import engine
from services.api.models import Incident
from services.api.routers.inventory import router as inventory_router
from services.api.routers.tasks import router as tasks_router


app = FastAPI(
    title="Brasaland Incident API",
    description="API para analizar incidentes de Brasaland",
    version="1.0.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# VALIDACIONES DE INCIDENTES
# ============================================================

VALID_LOCATIONS = {
    "COL-01",
    "COL-02",
    "COL-03",
    "COL-04",
    "COL-05",
    "COL-06",
    "COL-07",
    "COL-08",
    "COL-09",
    "COL-10",
    "FLA-01",
    "FLA-02",
    "FLA-03",
    "FLA-04",
}


VALID_CATEGORIES = {
    "CUSTOMER_COMPLAINT",
    "EQUIPMENT",
    "SUPPLY",
    "FOOD_QUALITY",
    "STAFF",
}


VALID_STATUSES = {
    "OPEN",
    "CLOSED",
    "DISCARDED",
}


REQUIRED_COLUMNS = {
    "location_id",
    "category",
    "description",
    "reporter_id",
    "status",
    "satisfaction_score",
}


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "service": "brasaland-incident-api",
    }


# ============================================================
# INCIDENTS SUMMARY
# ============================================================

@app.get("/api/incidents/summary")
def incidents_summary():
    """
    Devuelve el resumen de incidentes utilizado por el dashboard.
    """

    with Session(engine) as db:
        incidents = db.exec(
            select(Incident)
        ).all()

    total_records = len(incidents)

    by_category = {}

    for incident in incidents:
        category = incident.category

        if category not in by_category:
            by_category[category] = 0

        by_category[category] += 1

    by_status = {}

    for incident in incidents:
        status = incident.status

        if status not in by_status:
            by_status[status] = 0

        by_status[status] += 1

    closed_incidents = [
        incident
        for incident in incidents
        if incident.status == "CLOSED"
    ]

    closed_scores = [
        incident.satisfaction_score
        for incident in closed_incidents
        if incident.satisfaction_score is not None
    ]

    average_satisfaction = (
        round(
            sum(closed_scores) / len(closed_scores),
            2,
        )
        if closed_scores
        else None
    )

    return {
        "total_records": total_records,
        "by_category": by_category,
        "by_status": by_status,
        "closed_incidents": len(closed_incidents),
        "average_satisfaction": average_satisfaction,
    }


# ============================================================
# INCIDENTS ANALYSIS
# ============================================================

@app.post(
    "/api/incidents/analyze",
    status_code=202,
)
async def analyze_incidents(file: UploadFile = File(...)):
    from pathlib import Path
    from uuid import uuid4

    from services.tasks import analyze_incidents_csv_task

    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="El archivo debe ser un CSV.",
        )

    upload_dir = Path("data/async_uploads").resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_path = upload_dir / f"{uuid4().hex}.csv"

    max_size = 10 * 1024 * 1024
    total_size = 0

    try:
        with file_path.open("wb") as destination:
            while chunk := await file.read(1024 * 1024):
                total_size += len(chunk)

                if total_size > max_size:
                    raise HTTPException(
                        status_code=413,
                        detail="El CSV supera el l?mite de 10 MB.",
                    )

                destination.write(chunk)

        if total_size == 0:
            raise HTTPException(
                status_code=400,
                detail="El archivo est? vac?o.",
            )

        task = analyze_incidents_csv_task.delay(str(file_path))

    except HTTPException:
        file_path.unlink(missing_ok=True)
        raise

    except Exception as error:
        file_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=503,
            detail="No se pudo enviar el an?lisis a Celery.",
        ) from error

    finally:
        await file.close()

    return {"task_id": task.id}


# ============================================================
# ROUTERS DE AUTENTICACIÓN
# ============================================================

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(profiles_router)


# ============================================================
# ROUTER DE INVENTARIO
# ============================================================

app.include_router(inventory_router)


# ============================================================
# ROUTER DE TAREAS ASÍNCRONAS
# ============================================================

app.include_router(tasks_router)
