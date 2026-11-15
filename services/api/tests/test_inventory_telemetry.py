import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from services.api.database import get_db
from services.api.main import app
from services.api.routers import inventory as inventory_router


@pytest.fixture
def inventory_client(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def override_get_db():
        with Session(engine) as session:
            yield session

    captured_events = []

    monkeypatch.setattr(
        inventory_router,
        "send_telemetry_event",
        lambda event_type, properties: (
            captured_events.append((event_type, properties)) or True
        ),
    )
    monkeypatch.setattr(
        inventory_router,
        "find_supplier",
        lambda supplier_name, ingredient: {
            "id": 1,
            "name": supplier_name,
        },
    )

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client, captured_events

    app.dependency_overrides.clear()
    SQLModel.metadata.drop_all(engine)
    engine.dispose()


def create_ingredient(client):
    response = client.post(
        "/inventory/products",
        json={
            "name": "Carne de prueba",
            "sku": "MEAT-TEST",
            "unit": "kg",
            "category": "carne",
            "country": "Colombia",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_inbound_order_emits_telemetry(inventory_client):
    client, events = inventory_client
    ingredient = create_ingredient(client)

    response = client.post(
        "/inventory/orders/inbound",
        json={
            "ingredient_id": ingredient["id"],
            "quantity": 10,
            "supplier_name": "Carnes del Valle S.A.S.",
            "location_id": 1,
            "user_uuid": "test-user",
        },
    )

    assert response.status_code == 201
    assert len(events) == 1

    event_type, properties = events[0]
    assert event_type == "inbound_order_created"
    assert properties["supplier_id"] == "1"
    assert properties["currency"] == "COP"
    assert properties["country"] == "CO"
    assert properties["order_id"] == str(response.json()["id"])


def test_outbound_order_emits_telemetry(inventory_client):
    client, events = inventory_client
    ingredient = create_ingredient(client)

    inbound = client.post(
        "/inventory/orders/inbound",
        json={
            "ingredient_id": ingredient["id"],
            "quantity": 10,
            "supplier_name": "Carnes del Valle S.A.S.",
            "location_id": 1,
            "user_uuid": "test-user",
        },
    )
    assert inbound.status_code == 201
    events.clear()

    response = client.post(
        "/inventory/orders/outbound",
        json={
            "ingredient_id": ingredient["id"],
            "quantity": 2,
            "reason": "consumption",
            "location_id": 1,
            "user_uuid": "test-user",
        },
    )

    assert response.status_code == 201
    assert len(events) == 1
    assert events[0][0] == "outbound_order_created"
    assert events[0][1]["currency"] == "COP"
    assert events[0][1]["order_id"] == str(response.json()["id"])


def test_waste_order_emits_both_telemetry_events(inventory_client):
    client, events = inventory_client
    ingredient = create_ingredient(client)

    inbound = client.post(
        "/inventory/orders/inbound",
        json={
            "ingredient_id": ingredient["id"],
            "quantity": 10,
            "supplier_name": "Carnes del Valle S.A.S.",
            "location_id": 1,
            "user_uuid": "test-user",
        },
    )
    assert inbound.status_code == 201
    events.clear()

    response = client.post(
        "/inventory/orders/outbound",
        json={
            "ingredient_id": ingredient["id"],
            "quantity": 2,
            "reason": "waste",
            "waste_reason": "expired",
            "location_id": 1,
            "user_uuid": "test-user",
        },
    )

    assert response.status_code == 201
    assert [event[0] for event in events] == [
        "outbound_order_created",
        "stock_waste_registered",
    ]
    assert events[0][1]["reason"] == "expired"
    assert events[1][1]["reason"] == "expired"
    assert events[1][1]["order_id"] == str(response.json()["id"])


def test_waste_order_requires_specific_reason(inventory_client):
    client, events = inventory_client
    ingredient = create_ingredient(client)

    response = client.post(
        "/inventory/orders/outbound",
        json={
            "ingredient_id": ingredient["id"],
            "quantity": 1,
            "reason": "waste",
            "location_id": 1,
            "user_uuid": "test-user",
        },
    )

    assert response.status_code == 422
    assert events == []

def test_stock_threshold_triggers_when_stock_crosses_threshold(inventory_client):
    client, events = inventory_client
    ingredient = create_ingredient(client)

    inbound = client.post(
        "/inventory/orders/inbound",
        json={
            "ingredient_id": ingredient["id"],
            "quantity": 10,
            "supplier_name": "Carnes del Valle S.A.S.",
            "location_id": 1,
            "user_uuid": "test-user",
        },
    )
    assert inbound.status_code == 201

    threshold = client.put(
        "/inventory/thresholds",
        json={
            "ingredient_id": ingredient["id"],
            "location_id": 1,
            "threshold_quantity": 8,
        },
    )
    assert threshold.status_code == 200
    events.clear()

    outbound = client.post(
        "/inventory/orders/outbound",
        json={
            "ingredient_id": ingredient["id"],
            "quantity": 2,
            "reason": "consumption",
            "location_id": 1,
            "user_uuid": "test-user",
        },
    )
    assert outbound.status_code == 201

    threshold_events = [
        event for event in events
        if event[0] == "stock_threshold_triggered"
    ]
    assert len(threshold_events) == 1
    properties = threshold_events[0][1]
    assert properties["quantity"] == 8
    assert properties["threshold_quantity"] == 8
    assert properties["location_id"] == "1"


def test_direct_stock_edit_is_rejected_and_tracked(inventory_client):
    client, events = inventory_client
    ingredient = create_ingredient(client)

    response = client.post(
        f"/inventory/products/{ingredient['id']}/stock",
        json={
            "location_id": 1,
            "operation_type": "manual_adjustment",
        },
    )

    assert response.status_code == 409
    assert len(events) == 1
    event_type, properties = events[0]
    assert event_type == "direct_stock_edit_rejected"
    assert properties["rejection_result"] == "rejected"
    assert properties["operation_type"] == "manual_adjustment"


def test_price_variance_over_ten_percent_is_tracked(inventory_client):
    client, events = inventory_client
    ingredient = create_ingredient(client)

    base_order = {
        "ingredient_id": ingredient["id"],
        "quantity": 10,
        "supplier_name": "Carnes del Valle S.A.S.",
        "location_id": 1,
        "user_uuid": "test-user",
        "currency": "COP",
    }

    first = client.post(
        "/inventory/orders/inbound",
        json={**base_order, "unit_price": 100},
    )
    assert first.status_code == 201

    events.clear()

    second = client.post(
        "/inventory/orders/inbound",
        json={**base_order, "unit_price": 120},
    )
    assert second.status_code == 201

    variance_events = [
        event for event in events
        if event[0] == "ingredient_price_variance_detected"
    ]
    assert len(variance_events) == 1
    properties = variance_events[0][1]
    assert properties["previous_price"] == 100
    assert properties["new_price"] == 120
    assert properties["variance_percentage"] == 20
    assert properties["supplier_id"] == "1"
