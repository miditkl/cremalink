"""
This module provides extractor functions that pull data from a raw monitor frame.
"""
from __future__ import annotations

import base64
from typing import Any, Tuple

from cremalink.parsing.monitor.frame import MonitorFrame


def extract_fields_from_b64(
    raw_b64: str,
) -> Tuple[dict[str, Any], list[str], list[str], MonitorFrame | None]:
    """
    Parses a base64-encoded monitor string into a low-level MonitorFrame
    and extracts its fields into a dictionary.

    This function serves as the first step in the decoding pipeline. It handles
    the initial, structural parsing of the byte frame and populates a dictionary
    with the raw integer and byte values.

    Args:
        raw_b64: The base64-encoded monitor data string.

    Returns:
        A tuple containing:
        - A dictionary of the extracted raw fields.
        - A list of any warnings generated during parsing.
        - A list of any errors encountered during parsing.
        - The parsed `MonitorFrame` object, or None if parsing failed.
    """
    parsed: dict[str, Any] = {}
    warnings: list[str] = []
    errors: list[str] = []
    frame: MonitorFrame | None = None
    
    # --- Step 1: Decode the raw bytes into a MonitorFrame ---
    try:
        frame = MonitorFrame.from_b64(raw_b64)
    except Exception as exc:
        # If frame parsing fails, record the error and exit.
        errors.append(f"parse_failed: {exc}")
        try:
            # As a fallback, try to at least record the length of the raw data.
            raw = base64.b64decode(raw_b64)
            parsed["raw_length"] = len(raw)
        except Exception:
            pass
        return parsed, warnings, errors, frame

    # --- Step 2: Populate the 'parsed' dictionary with the frame's fields ---
    parsed.update(
        {
            "accessory": frame.accessory,
            "switches": list(frame.switches),
            "alarms": list(frame.alarms),
            "status": frame.status,
            "action": frame.action,
            "progress": frame.progress,
            "direction": frame.direction,
            "request_id": frame.request_id,
            "answer_required": frame.answer_required,
            "timestamp": frame.timestamp.hex() if frame.timestamp else "",
            "extra": frame.extra.hex() if frame.extra else "",
        }
    )

    return parsed, warnings, errors, frame
