"""Pruebas unitarias de las transformaciones del pipeline Brasaland."""

from datetime import datetime
from decimal import Decimal

import pytest

from data.pipelines.pipeline import (
    aggregate_weekly_events,
    calculate_weekly_ratios,
    validate_telemetry_events,
)


def make_event(event_type, **extra_tags):
    return {
        "timestamp": datetime(2026, 11, 18, 10, 0),
        "event_type": event_type,
        "tags": {
            "location_id": "test-location",
            "country": "CO",
            "currency": "COP",
            **extra_tags,
        },
    }


def test_validate_telemetry_events_accepts_valid_cost():
    events = [make_event("inbound_order_created", total_cost="200")]
    assert validate_telemetry_events.fn(events) == events


def test_validate_telemetry_events_rejects_missing_cost():
    events = [make_event("stock_waste_registered")]
    with pytest.raises(ValueError, match="Costo monetario faltante"):
        validate_telemetry_events.fn(events)


def test_validate_telemetry_events_rejects_wrong_currency():
    events = [make_event("stock_threshold_triggered", currency="USD")]
    with pytest.raises(ValueError, match="Moneda incompatible"):
        validate_telemetry_events.fn(events)


def test_aggregate_weekly_events_calculates_base_kpis():
    events = [
        make_event("inbound_order_created", total_cost="200"),
        make_event("stock_waste_registered", total_cost="30"),
        make_event("stock_threshold_triggered"),
        make_event("stock_threshold_triggered"),
        make_event("ingredient_price_variance_detected"),
    ]

    rows = aggregate_weekly_events.fn(
        validate_telemetry_events.fn(events)
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["week_start"].isoformat() == "2026-11-16"
    assert row["total_purchase_cost"] == Decimal("200")
    assert row["total_waste_cost"] == Decimal("30")
    assert row["stockout_events_count"] == 2
    assert row["price_alert_events_count"] == 1


def test_calculate_weekly_ratios():
    rows = [{
        "total_purchase_cost": Decimal("200"),
        "total_waste_cost": Decimal("30"),
    }]

    result = calculate_weekly_ratios.fn(rows)

    assert result[0]["waste_ratio"] == Decimal("0.15")
    assert "waste_ratio" not in rows[0]


def test_calculate_weekly_ratios_with_zero_purchases():
    rows = [{
        "total_purchase_cost": Decimal("0"),
        "total_waste_cost": Decimal("30"),
    }]

    result = calculate_weekly_ratios.fn(rows)

    assert result[0]["waste_ratio"] == Decimal("0")
