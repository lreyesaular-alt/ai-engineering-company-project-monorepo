
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from services.api.main import app
from services.api.routers import telemetry
from services.telemetry import analysis


client = TestClient(app)

START = "2026-11-08T00:00:00Z"
END = "2026-11-15T00:00:00Z"

REPORT_URL = (
    f"/telemetry/report?start_date={START}&end_date={END}"
)


@pytest.fixture(autouse=True)
def clear_report_cache():
    """Isolate cache state between tests."""
    telemetry._report_cache.clear()
    yield
    telemetry._report_cache.clear()


@pytest.fixture
def mock_metrics():
    """Avoid real database connections in endpoint tests."""
    with (
        patch.object(
            telemetry,
            "events_per_day",
            return_value=[{"date": "2026-11-11", "count": 3}],
        ) as events,
        patch.object(
            telemetry,
            "error_rate_by_type",
            return_value=[],
        ) as errors,
        patch.object(
            telemetry,
            "api_latency_by_endpoint",
            return_value=[],
        ) as latency,
    ):
        yield events, errors, latency


def test_report_returns_three_metrics(mock_metrics):
    response = client.get(REPORT_URL)

    assert response.status_code == 200

    body = response.json()

    assert set(body) == {"period", "metrics"}
    assert body["period"]["from"] == (
        "2026-11-08T00:00:00+00:00"
    )
    assert body["period"]["to"] == (
        "2026-11-15T00:00:00+00:00"
    )

    assert set(body["metrics"]) == {
        "events_per_day",
        "error_rate_by_type",
        "api_latency_by_endpoint",
    }

    assert body["metrics"]["events_per_day"] == [
        {"date": "2026-11-11", "count": 3}
    ]

    for metric in mock_metrics:
        metric.assert_called_once()


@pytest.mark.parametrize(
    "query",
    [
        "?start_date=invalid",
        "?end_date=invalid",
        "?start_date=2026-11-15T00:00:00Z"
        "&end_date=2026-11-08T00:00:00Z",
        "?start_date=2026-11-15T00:00:00Z"
        "&end_date=2026-11-15T00:00:00Z",
    ],
)
def test_report_rejects_invalid_periods(query, mock_metrics):
    response = client.get("/telemetry/report" + query)

    assert response.status_code == 422

    for metric in mock_metrics:
        metric.assert_not_called()


def test_report_accepts_timezone_offsets(mock_metrics):
    response = client.get(
        "/telemetry/report"
        "?start_date=2026-11-08T01:00:00%2B01:00"
        "&end_date=2026-11-15T01:00:00%2B01:00"
    )

    assert response.status_code == 200
    assert response.json()["period"] == {
        "from": "2026-11-08T00:00:00+00:00",
        "to": "2026-11-15T00:00:00+00:00",
    }


def test_report_defaults_to_seven_days(mock_metrics):
    response = client.get("/telemetry/report")

    assert response.status_code == 200

    period = response.json()["period"]
    start = datetime.fromisoformat(period["from"])
    end = datetime.fromisoformat(period["to"])

    assert end - start == timedelta(days=7)
    assert end.tzinfo is not None


def test_report_uses_cache(mock_metrics):
    first = client.get(REPORT_URL)
    second = client.get(REPORT_URL)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()

    for metric in mock_metrics:
        metric.assert_called_once()

    assert len(telemetry._report_cache) == 1


def test_report_cache_expires_after_60_seconds(mock_metrics):
    """Verify expired entries are recalculated without patching time."""
    first = client.get(REPORT_URL)

    assert first.status_code == 200
    assert len(telemetry._report_cache) == 1

    cache_key = next(iter(telemetry._report_cache))
    expires_at, cached_report = telemetry._report_cache[cache_key]

    # Force expiration without changing Python's global clock.
    telemetry._report_cache[cache_key] = (
        expires_at - telemetry.REPORT_CACHE_TTL_SECONDS - 1,
        cached_report,
    )

    second = client.get(REPORT_URL)

    assert second.status_code == 200

    for metric in mock_metrics:
        assert metric.call_count == 2


def test_report_returns_503_on_database_error(mock_metrics):
    mock_metrics[0].side_effect = SQLAlchemyError(
        "simulated database error"
    )

    response = client.get(REPORT_URL)

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Telemetry report unavailable"
    )


def make_fake_connection(rows):
    """Create a mocked read-only SQLAlchemy connection."""
    connection = MagicMock()
    connection.execute.return_value.mappings.return_value.all.return_value = rows

    context = MagicMock()
    context.__enter__.return_value = connection
    context.__exit__.return_value = False

    return context, connection


def test_events_per_day_groups_dates():
    rows = [
        {"timestamp": "2026-11-11T10:00:00Z"},
        {"timestamp": "2026-11-11T11:00:00Z"},
        {"timestamp": "2026-11-12T10:00:00Z"},
    ]

    context, connection = make_fake_connection(rows)

    with patch.object(
        analysis.engine,
        "connect",
        return_value=context,
    ):
        result = analysis.events_per_day(
            datetime(2026, 11, 8, tzinfo=timezone.utc),
            datetime(2026, 11, 15, tzinfo=timezone.utc),
        )

    assert result == [
        {"date": "2026-11-11", "count": 2},
        {"date": "2026-11-12", "count": 1},
    ]

    sql = str(connection.execute.call_args.args[0])
    assert "timestamp >= :start_date" in sql
    assert "timestamp < :end_date" in sql


def test_error_rate_by_type_calculates_percentage():
    rows = [
        {
            "timestamp": "2026-11-11T10:00:00Z",
            "event_type": "api_request_failed",
            "level": "error",
        },
        {
            "timestamp": "2026-11-11T11:00:00Z",
            "event_type": "api_request_failed",
            "level": "info",
        },
    ]

    context, connection = make_fake_connection(rows)

    with patch.object(
        analysis.engine,
        "connect",
        return_value=context,
    ):
        result = analysis.error_rate_by_type(
            datetime(2026, 11, 8, tzinfo=timezone.utc),
            datetime(2026, 11, 15, tzinfo=timezone.utc),
        )

    assert result == [
        {
            "date": "2026-11-11",
            "event_type": "api_request_failed",
            "total_events": 2,
            "error_events": 1,
            "error_rate": 50.0,
        }
    ]

    sql = str(connection.execute.call_args.args[0])
    assert "timestamp >= :start_date" in sql
    assert "timestamp < :end_date" in sql


def test_api_latency_ignores_invalid_values():
    rows = [
        {
            "timestamp": "2026-11-11T10:00:00Z",
            "endpoint_id": "inventory",
            "duration_ms": "100",
        },
        {
            "timestamp": "2026-11-11T11:00:00Z",
            "endpoint_id": "inventory",
            "duration_ms": "200",
        },
        {
            "timestamp": "2026-11-11T12:00:00Z",
            "endpoint_id": "inventory",
            "duration_ms": "invalid",
        },
        {
            "timestamp": "2026-11-11T13:00:00Z",
            "endpoint_id": "",
            "duration_ms": "300",
        },
        {
            "timestamp": "2026-11-11T14:00:00Z",
            "endpoint_id": "",
            "duration_ms": "300",
        },
        {
            "timestamp": "2026-11-11T15:00:00Z",
            "endpoint_id": "inventory",
            "duration_ms": "-5",
        },
    ]

    context, connection = make_fake_connection(rows)

    with patch.object(
        analysis.engine,
        "connect",
        return_value=context,
    ):
        result = analysis.api_latency_by_endpoint(
            datetime(2026, 11, 8, tzinfo=timezone.utc),
            datetime(2026, 11, 15, tzinfo=timezone.utc),
        )

    assert result == [
        {
            "endpoint_id": "inventory",
            "request_count": 2,
            "average_latency_ms": 150.0,
        }
    ]

    sql = str(connection.execute.call_args.args[0])
    assert "event_type = 'api_latency_recorded'" in sql
    assert "timestamp >= :start_date" in sql
    assert "timestamp < :end_date" in sql


@pytest.mark.parametrize(
    "metric",
    [
        analysis.events_per_day,
        analysis.error_rate_by_type,
        analysis.api_latency_by_endpoint,
    ],
)
def test_metrics_return_empty_list_without_events(metric):
    context, _ = make_fake_connection([])

    with patch.object(
        analysis.engine,
        "connect",
        return_value=context,
    ):
        result = metric(
            datetime(2026, 11, 8, tzinfo=timezone.utc),
            datetime(2026, 11, 15, tzinfo=timezone.utc),
        )

    assert result == []
