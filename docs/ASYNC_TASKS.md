
# Async Tasks with Celery, Redis and Flower

## Overview

This project uses FastAPI, Redis and Celery to process long-running tasks asynchronously.

- FastAPI receives requests and returns a task ID.
- Redis acts as the message broker and result backend.
- Celery executes background tasks independently.
- Flower monitors task execution.
- PostgreSQL stores permanently failed tasks in a dead-letter queue (DLQ).

## Requirements

- Python virtual environment
- Docker Desktop
- PostgreSQL connection configured in `services/api/.env`

Install dependencies:

    python -m pip install -r services/api/requirements.txt

## Start Redis and Flower

From the repository root:

    docker compose up -d redis flower

Redis runs on port 6379.

Flower dashboard: http://localhost:5555

## Start the Celery worker

Open a terminal with the virtual environment activated:

    python -m celery -A services.celery_app:celery_app worker --loglevel=info --pool=solo -E -n async-worker@%h

The solo pool is used for local Windows development.

## Start FastAPI

In another terminal:

    python -m uvicorn services.api.main:app --host 127.0.0.1 --port 8001

API documentation: http://127.0.0.1:8001/docs

## Enqueue a test task

Endpoint:

    POST /tasks

Example JSON body:

    {"seconds": 5}

Expected response:

    HTTP 202 Accepted
    {"task_id": "generated-task-id"}

Check the task status:

    GET /tasks/{task_id}

Possible statuses: pending, started, success and failure.

## Analyze incidents asynchronously

Endpoint:

    POST /api/incidents/analyze

Upload a CSV using multipart/form-data with the field name `file`.

FastAPI saves the CSV temporarily and sends only its file path to Celery.

The API responds with HTTP 202 Accepted and a task ID.

Retrieve the result using:

    GET /tasks/{task_id}

Maximum CSV upload size: 10 MB.

Temporary CSV files are deleted after successful processing or permanent failure.

## Retries and dead-letter queue

Tasks support up to three retries with exponential backoff.

The test task retries ValueError exceptions.

The CSV analysis task retries OSError exceptions.

Invalid CSV content fails without retrying.

Permanent failures are stored in PostgreSQL in the `dead_letter_tasks` table.

Each record contains:

- Task ID
- Task name
- Retry count
- Full error traceback
- Failure timestamp

## Monitoring

Open Flower:

http://localhost:5555

Flower displays workers, task execution, successful tasks and failures.

## Stop services

Stop FastAPI and Celery using Ctrl+C in their terminals.

Stop Redis and Flower:

    docker compose down

## Performance verification

A local test using a small CSV returned HTTP 202 Accepted in 7.6 milliseconds.

The target is under 200 milliseconds.

This is a local development measurement, not a production performance guarantee.
