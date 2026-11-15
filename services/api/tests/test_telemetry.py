
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from services.api.main import app


client = TestClient(app)


def valid_event():
    return {
        "eventId": str(uuid4()),
        "timestamp": "2026-11-11T12:00:00Z",
        "sessionId": None,
        "userId": None,
        "event_type": "page_viewed",
        "schemaVersion": "1.0.0",
        "requestId": None,
        "properties": {
            "page_id": "dashboard",
            "page_section": "inventory",
        },
    }


@pytest.fixture(autouse=True)
def mock_telemetry_database():
    """Evita escribir datos reales en Supabase durante los tests."""
    connection = MagicMock()
    transaction = MagicMock()
    transaction.__enter__.return_value = connection
    transaction.__exit__.return_value = False

    with patch(
        "services.api.routers.telemetry.engine.begin",
        return_value=transaction,
    ) as begin:
        yield begin, connection


def test_telemetry_accepts_valid_event(mock_telemetry_database):
    begin, connection = mock_telemetry_database

    response = client.post(
        "/telemetry/events",
        json={"events": [valid_event()]},
    )

    assert response.status_code == 200
    assert response.json() == {
        "received": 1,
        "stored": 1,
        "rejected": 0,
    }
    begin.assert_called_once()
    connection.execute.assert_called_once()

    rows = connection.execute.call_args.args[1]
    assert len(rows) == 1
    assert rows[0]["service"] == "brasaland-backoffice"
    assert rows[0]["event_type"] == "page_viewed"


def test_telemetry_accepts_batch(mock_telemetry_database):
    begin, connection = mock_telemetry_database

    response = client.post(
        "/telemetry/events",
        json={"events": [valid_event(), valid_event()]},
    )

    assert response.status_code == 200
    assert response.json() == {
        "received": 2,
        "stored": 2,
        "rejected": 0,
    }

    begin.assert_called_once()
    connection.execute.assert_called_once()
    assert len(connection.execute.call_args.args[1]) == 2


@pytest.mark.parametrize(
    "change",
    [
        lambda event: event.pop("eventId"),
        lambda event: event.pop("userId"),
        lambda event: event.update(event_type="unknown_event"),
        lambda event: event["properties"].update(
            email="test@example.com"
        ),
        lambda event: event["properties"].pop("page_id"),
        lambda event: event.update(schemaVersion="2.0.0"),
    ],
    ids=[
        "missing_event_id",
        "missing_nullable_envelope_field",
        "unknown_event",
        "unknown_property",
        "missing_required_property",
        "wrong_schema_version",
    ],
)
def test_telemetry_rejects_invalid_event(
    change,
    mock_telemetry_database,
):
    begin, connection = mock_telemetry_database
    event = valid_event()
    change(event)

    response = client.post(
        "/telemetry/events",
        json={"events": [event]},
    )

    assert response.status_code == 200
    assert response.json() == {
        "received": 1,
        "stored": 0,
        "rejected": 1,
    }
    begin.assert_not_called()
    connection.execute.assert_not_called()


def test_telemetry_accepts_mixed_batch(mock_telemetry_database):
    begin, connection = mock_telemetry_database

    invalid_event = valid_event()
    invalid_event["event_type"] = "unknown_event"

    response = client.post(
        "/telemetry/events",
        json={"events": [valid_event(), invalid_event]},
    )

    assert response.status_code == 200
    assert response.json() == {
        "received": 2,
        "stored": 1,
        "rejected": 1,
    }

    begin.assert_called_once()
    connection.execute.assert_called_once()
    assert len(connection.execute.call_args.args[1]) == 1


def test_telemetry_rejects_non_object_event(
    mock_telemetry_database,
):
    begin, connection = mock_telemetry_database

    response = client.post(
        "/telemetry/events",
        json={"events": [valid_event(), "invalid"]},
    )

    assert response.status_code == 200
    assert response.json() == {
        "received": 2,
        "stored": 1,
        "rejected": 1,
    }
    begin.assert_called_once()
    connection.execute.assert_called_once()


def test_telemetry_returns_503_on_database_error(
    mock_telemetry_database,
):
    begin, connection = mock_telemetry_database
    connection.execute.side_effect = SQLAlchemyError(
        "simulated database error"
    )

    response = client.post(
        "/telemetry/events",
        json={"events": [valid_event()]},
    )

    assert response.status_code == 503
    begin.assert_called_once()


def test_telemetry_rejects_empty_batch(
    mock_telemetry_database,
):
    begin, _ = mock_telemetry_database

    response = client.post(
        "/telemetry/events",
        json={"events": []},
    )

    assert response.status_code == 422
    begin.assert_not_called()


def test_telemetry_rejects_more_than_20_events(
    mock_telemetry_database,
):
    begin, _ = mock_telemetry_database

    response = client.post(
        "/telemetry/events",
        json={"events": [valid_event() for _ in range(21)]},
    )

    assert response.status_code == 422
    begin.assert_not_called()
