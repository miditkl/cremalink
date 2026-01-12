"""
This module contains the primary functions for decoding a raw monitor payload
into a structured `MonitorSnapshot`.
"""
from __future__ import annotations

import base64
import datetime as dt
from typing import Any

from cremalink.parsing.monitor.extractors import extract_fields_from_b64
from cremalink.parsing.monitor.model import MonitorSnapshot


def decode_monitor_b64(raw_b64: str) -> bytes:
    """
    A simple wrapper for base64 decoding that provides a more specific error message.
    """
    try:
        return base64.b64decode(raw_b64)
    except Exception as exc:
        raise ValueError(f"Failed to decode monitor base64: {exc}") from exc


def build_monitor_snapshot(
    payload: dict[str, Any],
    source: str = "local",
    device_id: str | None = None,
) -> MonitorSnapshot:
    """
    Constructs a `MonitorSnapshot` from a raw payload dictionary.

    This function orchestrates the decoding process:
    1. It extracts the base64-encoded monitor string from the input payload.
    2. It decodes the base64 string into raw bytes.
    3. It calls `extract_fields_from_b64` to parse the raw bytes into a
       low-level dictionary and a `MonitorFrame`.
    4. It bundles all this information into a `MonitorSnapshot` object.

    Args:
        payload: The raw dictionary payload, typically from the local server or cloud API.
        source: The origin of the data (e.g., 'local', 'cloud').
        device_id: The identifier of the device.

    Returns:
        A populated `MonitorSnapshot` instance.
    """
    # The base64 data can be in a few different places depending on the source.
    raw_b64 = payload.get("monitor_b64") or payload.get("monitor", {}).get("data", {}).get("value")
    
    # If no base64 data is found, return an empty snapshot with a warning.
    if not raw_b64:
        return MonitorSnapshot(
            raw=b"",
            raw_b64="",
            received_at=dt.datetime.fromtimestamp(payload.get("received_at") or dt.datetime.now(dt.UTC).timestamp()),
            parsed={},
            warnings=["no monitor_b64 in payload"],
            errors=[],
            source=source,
            device_id=device_id,
        )

    # Decode the base64 string and then extract the low-level fields.
    raw = decode_monitor_b64(raw_b64)
    parsed, warnings, errors, frame = extract_fields_from_b64(raw_b64)
    
    # Assemble the final snapshot object.
    return MonitorSnapshot(
        raw=raw,
        raw_b64=raw_b64,
        received_at=dt.datetime.fromtimestamp(payload.get("received_at") or dt.datetime.now(dt.UTC).timestamp()),
        parsed=parsed,
        warnings=warnings,
        errors=errors,
        source=source,
        device_id=device_id,
        frame=frame,
    )
