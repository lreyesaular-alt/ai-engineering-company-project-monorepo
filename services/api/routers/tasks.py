
from celery.result import AsyncResult
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from services.celery_app import celery_app
from services.tasks import test_async_task

router = APIRouter(tags=["Async Tasks"])


class TaskRequest(BaseModel):
    seconds: int = Field(default=5, ge=1, le=30)


@router.post("/tasks", status_code=status.HTTP_202_ACCEPTED)
def create_task(payload: TaskRequest):
    try:
        task = test_async_task.delay(payload.seconds)
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail="No se pudo enviar la tarea a Redis.",
        ) from error

    return {"task_id": task.id}


@router.get("/tasks/{task_id}")
def get_task_status(task_id: str):
    task = AsyncResult(task_id, app=celery_app)

    states = {
        "PENDING": "pending",
        "STARTED": "started",
        "SUCCESS": "success",
        "FAILURE": "failure",
        "RETRY": "pending",
    }

    response = {
        "task_id": task_id,
        "status": states.get(task.state, task.state.lower()),
    }

    if task.successful():
        response["result"] = task.result

    if task.failed():
        response["error"] = str(task.result)

    return response
