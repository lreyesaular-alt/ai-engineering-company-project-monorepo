
from uuid import uuid4

from fastapi.testclient import TestClient

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


def test_telemetry_accepts_valid_event():
    response = client.post(
        "/telemetry/events",
        json={"events": [valid_event()]},
    )

    assert response.status_code == 200
    assert response.json() == {"received": 1}


def test_telemetry_accepts_batch():
    response = client.post(
        "/telemetry/events",
        json={"events": [valid_event(), valid_event()]},
    )

    assert response.status_code == 200
    assert response.json() == {"received": 2}


def test_telemetry_rejects_missing_event_id():
    event = valid_event()
    del event["eventId"]

    response = client.post(
        "/telemetry/events",
        json={"events": [event]},
    )

    assert response.status_code == 422


def test_telemetry_rejects_missing_nullable_envelope_field():
    event = valid_event()
    del event["userId"]

    response = client.post(
        "/telemetry/events",
        json={"events": [event]},
    )

    assert response.status_code == 422


def test_telemetry_rejects_unknown_event():
    event = valid_event()
    event["event_type"] = "unknown_event"

    response = client.post(
        "/telemetry/events",
        json={"events": [event]},
    )

    assert response.status_code == 422


def test_telemetry_rejects_unknown_property():
    event = valid_event()
    event["properties"]["email"] = "test@example.com"

    response = client.post(
        "/telemetry/events",
        json={"events": [event]},
    )

    assert response.status_code == 422


def test_telemetry_rejects_missing_required_property():
    event = valid_event()
    del event["properties"]["page_id"]

    response = client.post(
        "/telemetry/events",
        json={"events": [event]},
    )

    assert response.status_code == 422


def test_telemetry_rejects_wrong_schema_version():
    event = valid_event()
    event["schemaVersion"] = "2.0.0"

    response = client.post(
        "/telemetry/events",
        json={"events": [event]},
    )

    assert response.status_code == 422


def test_telemetry_rejects_empty_batch():
    response = client.post(
        "/telemetry/events",
        json={"events": []},
    )

    assert response.status_code == 422


def test_telemetry_rejects_more_than_20_events():
    response = client.post(
        "/telemetry/events",
        json={"events": [valid_event() for _ in range(21)]},
    )

    assert response.status_code == 422
