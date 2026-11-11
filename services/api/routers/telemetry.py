
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from services.api.telemetry_models import TelemetryBatch


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


def validate_event(event: Any) -> None:
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

@router.post("/events")
def receive_telemetry(batch: TelemetryBatch):
    try:
        for event in batch.events:
            validate_event(event)

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error

    return {"received": len(batch.events)}

