"""
This module defines the high-level data model for a "monitor" data snapshot.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from cremalink.parsing.monitor.frame import MonitorFrame


@dataclass
class MonitorSnapshot:
    """
    Represents a single snapshot of the device's monitoring status.

    This dataclass acts as a container for all information related to a single
    monitor update from the device. It holds the raw data, timestamps, any
    parsed values, and metadata about the decoding process.

    Attributes:
        raw: The raw bytes of the monitor data payload.
        raw_b64: The base64-encoded string representation of the raw data.
        received_at: The timestamp when this snapshot was received.
        parsed: A dictionary to hold the successfully parsed key-value data.
        warnings: A list of any warnings generated during parsing.
        errors: A list of any errors encountered during parsing.
        source: The origin of the data (e.g., 'local' or 'cloud').
        device_id: The identifier of the device that sent the data.
        frame: A `MonitorFrame` instance if the raw bytes were successfully
               decoded into a low-level frame structure.
    """
    raw: bytes
    raw_b64: str
    received_at: datetime
    parsed: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    source: str = "local"
    device_id: Optional[str] = None
    frame: Optional[MonitorFrame] = None
