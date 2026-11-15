
from datetime import datetime

import pandas as pd
from sqlalchemy import text

from services.api.database import engine


def events_per_day(
    start_date: datetime,
    end_date: datetime,
) -> list[dict]:
    """Count telemetry events grouped by UTC day."""

    query = text("""
        SELECT timestamp
        FROM public.telemetry_events
        WHERE timestamp >= :start_date
          AND timestamp < :end_date
    """)

    with engine.connect() as connection:
        rows = connection.execute(
            query,
            {
                "start_date": start_date,
                "end_date": end_date,
            },
        ).mappings().all()

    df = pd.DataFrame(rows, columns=["timestamp"])

    if df.empty:
        return []

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        utc=True,
    )

    df["date"] = df["timestamp"].dt.strftime("%Y-%m-%d")

    result = (
        df.groupby("date")
        .size()
        .reset_index(name="count")
    )

    return result.to_dict(orient="records")


def error_rate_by_type(
    start_date: datetime,
    end_date: datetime,
) -> list[dict]:
    """Calculate error percentage grouped by day and event type."""

    query = text("""
        SELECT timestamp, event_type, level
        FROM public.telemetry_events
        WHERE timestamp >= :start_date
          AND timestamp < :end_date
    """)

    with engine.connect() as connection:
        rows = connection.execute(
            query,
            {
                "start_date": start_date,
                "end_date": end_date,
            },
        ).mappings().all()

    df = pd.DataFrame(
        rows,
        columns=["timestamp", "event_type", "level"],
    )

    if df.empty:
        return []

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        utc=True,
    )

    df["date"] = df["timestamp"].dt.strftime("%Y-%m-%d")
    df["is_error"] = df["level"].eq("error").astype(int)

    df = df.dropna(subset=["event_type"])

    if df.empty:
        return []

    result = (
        df.groupby(["date", "event_type"])
        .agg(
            total_events=("is_error", "count"),
            error_events=("is_error", "sum"),
        )
        .reset_index()
    )

    result["error_rate"] = (
        result["error_events"]
        / result["total_events"]
        * 100
    ).round(2)

    return result.to_dict(orient="records")


def api_latency_by_endpoint(
    start_date: datetime,
    end_date: datetime,
) -> list[dict]:
    """Calculate average API latency by endpoint."""

    query = text("""
        SELECT
            timestamp,
            tags ->> 'endpoint_id' AS endpoint_id,
            tags ->> 'duration_ms' AS duration_ms
        FROM public.telemetry_events
        WHERE timestamp >= :start_date
          AND timestamp < :end_date
          AND event_type = 'api_latency_recorded'
          AND tags ? 'endpoint_id'
          AND tags ? 'duration_ms'
    """)

    with engine.connect() as connection:
        rows = connection.execute(
            query,
            {
                "start_date": start_date,
                "end_date": end_date,
            },
        ).mappings().all()

    df = pd.DataFrame(
        rows,
        columns=["timestamp", "endpoint_id", "duration_ms"],
    )

    if df.empty:
        return []

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        utc=True,
    )

    df["duration_ms"] = pd.to_numeric(
        df["duration_ms"],
        errors="coerce",
    )

    df = df.dropna(
        subset=["endpoint_id", "duration_ms"]
    )

    df = df[
        df["endpoint_id"].str.strip().ne("")
        & df["duration_ms"].ge(0)
    ]

    if df.empty:
        return []

    result = (
        df.groupby("endpoint_id")
        .agg(
            request_count=("duration_ms", "count"),
            average_latency_ms=("duration_ms", "mean"),
        )
        .reset_index()
    )

    result["average_latency_ms"] = (
        result["average_latency_ms"].round(2)
    )

    return result.to_dict(orient="records")
