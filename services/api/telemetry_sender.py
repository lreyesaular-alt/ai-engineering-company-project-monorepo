import logging
import os
from datetime import datetime, timezone
from uuid import uuid4

import httpx


logger = logging.getLogger(__name__)

SCHEMA_VERSION = "1.0.0"


def send_telemetry_event(
    event_type: str,
    properties: dict,
) -> bool:
    endpoint = os.getenv("TELEMETRY_ENDPOINT")

    if not endpoint:
        logger.warning(
            "Telemetry event '%s' skipped: TELEMETRY_ENDPOINT is not configured.",
            event_type,
        )
        return False

    event = {
        "eventId": str(uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sessionId": None,
        "userId": None,
        "event_type": event_type,
        "schemaVersion": SCHEMA_VERSION,
        "requestId": None,
        "properties": properties,
    }

    try:
        response = httpx.post(
            endpoint,
            json={"events": [event]},
            timeout=3.0,
        )
        response.raise_for_status()
        return True
    except httpx.HTTPError:
        logger.exception(
            "Failed to send telemetry event '%s'.",
            event_type,
        )
        return False
