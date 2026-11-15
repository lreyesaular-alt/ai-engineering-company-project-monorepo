
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from services.api.database import engine
from services.api.telemetry_models import TelemetryEvent
from services.telemetry.analysis import (
    api_latency_by_endpoint,
    error_rate_by_type,
    events_per_day,
)


logger = logging.getLogger(__name__)

SCHEMA_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "telemetry"
    / "event-schemas.json"
)

with SCHEMA_PATH.open(encoding="utf-8") as schema_file:
    SCHEMA = json.load(schema_file)

EVENT_SCHEMAS = {
    event["event_type"]: event
    for event in SCHEMA["events"]
}

router = APIRouter(
    prefix="/telemetry",
    tags=["telemetry"],
)


# ---------------------------------------------------------
# TELEMETRY STORAGE
# ---------------------------------------------------------

class TelemetryIncomingBatch(BaseModel):
    events: list[Any] = Field(min_length=1, max_length=20)


def validate_property_type(
    name: str,
    value: Any,
    definition: dict[str, Any],
) -> None:
    expected_type = definition["type"]

    if isinstance(expected_type, list):
        valid_types = expected_type
    else:
        valid_types = [expected_type]

    type_checks = {
        "string": lambda v: isinstance(v, str),
        "number": lambda v: (
            isinstance(v, (int, float))
            and not isinstance(v, bool)
        ),
        "integer": lambda v: (
            isinstance(v, int) and not isinstance(v, bool)
        ),
        "boolean": lambda v: isinstance(v, bool),
        "object": lambda v: isinstance(v, dict),
        "array": lambda v: isinstance(v, list),
        "null": lambda v: v is None,
    }

    if not any(
        type_checks[t](value)
        for t in valid_types
        if t in type_checks
    ):
        raise ValueError(
            f"Invalid type for property '{name}'"
        )

    if value is None:
        return

    if "enum" in definition and value not in definition["enum"]:
        raise ValueError(
            f"Invalid value for property '{name}'"
        )

    if "minimum" in definition and value < definition["minimum"]:
        raise ValueError(
            f"Property '{name}' is below its minimum"
        )

    if "maximum" in definition and value > definition["maximum"]:
        raise ValueError(
            f"Property '{name}' exceeds its maximum"
        )


def validate_event(event: TelemetryEvent) -> None:
    if event.schemaVersion != SCHEMA["schemaVersion"]:
        raise ValueError("Unsupported schemaVersion")

    definition = EVENT_SCHEMAS.get(event.event_type)

    if definition is None:
        raise ValueError(
            f"Unknown event_type: {event.event_type}"
        )

    property_definitions = definition["properties"]
    properties = event.properties

    unknown_properties = (
        set(properties) - set(property_definitions)
    )

    if unknown_properties:
        raise ValueError(
            "Unknown properties: "
            + ", ".join(sorted(unknown_properties))
        )

    for name, property_schema in property_definitions.items():
        if (
            property_schema.get("required", False)
            and name not in properties
        ):
            raise ValueError(
                f"Missing required property: {name}"
            )

        if name in properties:
            validate_property_type(
                name,
                properties[name],
                property_schema,
            )


def event_to_row(event: TelemetryEvent) -> dict[str, Any]:
    error_events = {
        "login_failed",
        "credentials_rejected",
        "order_validation_failed",
        "direct_stock_edit_rejected",
        "api_request_failed",
        "frontend_error_captured",
        "permission_denied",
    }

    level = (
        "error"
        if event.event_type in error_events
        else "info"
    )

    return {
        "timestamp": event.timestamp,
        "service": "brasaland-backoffice",
        "event_type": event.event_type,
        "level": level,
        "value": None,
        "message": None,
        "tags": json.dumps(event.properties),
    }


INSERT_TELEMETRY_SQL = text(
    """
    INSERT INTO public.telemetry_events (
        "timestamp",
        service,
        event_type,
        level,
        value,
        message,
        tags
    )
    VALUES (
        :timestamp,
        :service,
        :event_type,
        :level,
        :value,
        :message,
        CAST(:tags AS jsonb)
    )
    """
)


@router.post("/events")
def receive_telemetry(batch: TelemetryIncomingBatch):
    received = len(batch.events)
    rejected = 0
    valid_rows = []

    for raw_event in batch.events:
        try:
            event = TelemetryEvent.model_validate(raw_event)
            validate_event(event)
            valid_rows.append(event_to_row(event))

        except (ValidationError, ValueError, TypeError):
            rejected += 1

    if not valid_rows:
        return {
            "received": received,
            "stored": 0,
            "rejected": rejected,
        }

    try:
        with engine.begin() as connection:
            connection.execute(
                INSERT_TELEMETRY_SQL,
                valid_rows,
            )

    except SQLAlchemyError:
        logger.exception(
            "Failed to store telemetry batch"
        )
        raise HTTPException(
            status_code=503,
            detail="Telemetry storage unavailable",
        )

    return {
        "received": received,
        "stored": len(valid_rows),
        "rejected": rejected,
    }


# ---------------------------------------------------------
# TELEMETRY REPORT
# ---------------------------------------------------------

REPORT_CACHE_TTL_SECONDS = 60

# Cache entries are keyed by the resolved UTC date window.
_report_cache: dict[
    tuple[str, str],
    tuple[float, dict[str, Any]],
] = {}

_report_cache_lock = Lock()


def parse_report_date(
    value: str | None,
    parameter_name: str,
) -> datetime | None:
    """Parse an ISO 8601 date or datetime into UTC."""

    if value is None:
        return None

    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=(
                f"{parameter_name} must be a valid "
                "ISO 8601 date or datetime"
            ),
        )

    if parsed.tzinfo is None:
        # Naive timestamps are interpreted as UTC.
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def resolve_report_period(
    start_date: str | None,
    end_date: str | None,
) -> tuple[datetime, datetime]:
    """Resolve optional dates to one UTC reporting window."""

    now = datetime.now(timezone.utc)

    # Round the default end time to the current minute
    # so repeated requests can reuse the 60-second cache.
    default_end = now.replace(second=0, microsecond=0)

    end = parse_report_date(end_date, "end_date")
    start = parse_report_date(start_date, "start_date")

    if end is None:
        end = default_end

    if start is None:
        start = end - timedelta(days=7)

    if start >= end:
        raise HTTPException(
            status_code=422,
            detail="start_date must be earlier than end_date",
        )

    if end > now:
        raise HTTPException(
            status_code=422,
            detail="end_date cannot be in the future",
        )

    return start, end


@router.get("/report")
def get_telemetry_report(
    start_date: str | None = None,
    end_date: str | None = None,
):
    """
    Return technical telemetry metrics for a UTC period.

    Defaults to the last seven days.
    Results are cached in memory for 60 seconds.
    """

    start, end = resolve_report_period(
        start_date=start_date,
        end_date=end_date,
    )

    start_iso = start.isoformat()
    end_iso = end.isoformat()

    cache_key = (start_iso, end_iso)

    # A single lock protects cache access and prevents
    # duplicate computations for concurrent requests.
    with _report_cache_lock:
        current_time = time.monotonic()

        cached_entry = _report_cache.get(cache_key)

        if cached_entry is not None:
            expires_at, cached_report = cached_entry

            if current_time < expires_at:
                return cached_report

        try:
            report = {
                "period": {
                    "from": start_iso,
                    "to": end_iso,
                },
                "metrics": {
                    "events_per_day": events_per_day(
                        start,
                        end,
                    ),
                    "error_rate_by_type": error_rate_by_type(
                        start,
                        end,
                    ),
                    "api_latency_by_endpoint": (
                        api_latency_by_endpoint(
                            start,
                            end,
                        )
                    ),
                },
            }

        except SQLAlchemyError:
            logger.exception(
                "Failed to generate telemetry report"
            )
            raise HTTPException(
                status_code=503,
                detail="Telemetry report unavailable",
            )

        # Remove expired entries before storing a new one.
        expired_keys = [
            key
            for key, (expires_at, _) in _report_cache.items()
            if expires_at <= time.monotonic()
        ]

        for key in expired_keys:
            del _report_cache[key]

        _report_cache[cache_key] = (
            time.monotonic() + REPORT_CACHE_TTL_SECONDS,
            report,
        )

        return report
