"""
This module defines the low-level structure of a "monitor" data frame.
It handles the byte-level decoding of the raw payload from the device.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass

from cremalink.core.binary import crc16_ccitt


@dataclass
class MonitorFrame:
    """
    Represents the decoded, low-level structure of a monitor data frame.

    This class takes the raw bytes from a monitor update and parses them into
    their fundamental components according to the device's binary protocol.
    This includes separating headers, payload, checksums, and timestamps.
    """
    # --- Frame Header/Metadata ---
    direction: int
    request_id: int
    answer_required: int
    # --- Core Payload Fields ---
    accessory: int
    switches: bytes
    alarms: bytes
    status: int
    action: int
    progress: int
    # --- Frame Footer/Extra Data ---
    timestamp: bytes
    extra: bytes
    # --- Raw Data ---
    raw: bytes
    raw_b64: str

    @classmethod
    def from_b64(cls, raw_b64: str) -> "MonitorFrame":
        """
        Decodes a base64 string into a structured MonitorFrame.

        This factory method performs the primary byte-level parsing, including:
        - Base64 decoding.
        - Length validation.
        - CRC-16 checksum verification.
        - Splitting the raw bytes into their respective fields (header, payload, etc.).

        Args:
            raw_b64: The base64-encoded monitor data string.

        Returns:
            A populated MonitorFrame instance.

        Raises:
            ValueError: If the data is malformed, too short, or fails the CRC check.
        """
        raw = base64.b64decode(raw_b64)
        if len(raw) < 4:
            raise ValueError("Raw data is too short to contain a monitor frame")
        
        # --- Unpack the outer frame ---
        direction = raw[0]
        length = raw[1]
        if length < 4 or len(raw) < length + 1:
            raise ValueError("Length byte inconsistent with payload")
        
        data = raw[2: length - 1]
        crc = raw[length - 1: length + 1]
        
        # --- Verify CRC ---
        if crc != crc16_ccitt(raw[: length - 1]):
            raise ValueError("CRC check failed")
        
        timestamp = raw[length + 1: length + 5]
        extra = raw[length + 5:]

        # --- Unpack the inner monitor data payload ---
        if len(data) < 2:
            raise ValueError("Monitor payload too short")
        request_id = data[0]
        answer_required = data[1]
        contents = data[2:]
        
        # This implementation assumes a "V2" frame structure with 13 bytes of contents.
        if len(contents) != 13:
            raise ValueError("Monitor contents expected to be 13 bytes for V2 frames")
        
        accessory = contents[0]
        switches = contents[1:3]
        # Alarms are non-contiguous in the payload, so they are concatenated here.
        alarms = contents[3:5] + contents[8:10]
        status = contents[5]
        action = contents[6]
        progress = contents[7]

        return cls(
            direction=direction,
            request_id=request_id,
            answer_required=answer_required,
            accessory=accessory,
            switches=switches,
            alarms=alarms,
            status=status,
            action=action,
            progress=progress,
            timestamp=timestamp,
            extra=extra,
            raw=raw,
            raw_b64=raw_b64,
        )

    def as_dict(self) -> dict:
        """
        Returns a dictionary representation of the frame's contents.
        This is useful for serialization or debugging.
        """
        return {
            "direction": self.direction,
            "request_id": self.request_id,
            "answer_required": self.answer_required,
            "accessory": self.accessory,
            "switches": list(self.switches),
            "alarms": list(self.alarms),
            "status": self.status,
            "action": self.action,
            "progress": self.progress,
            "timestamp": self.timestamp.hex() if self.timestamp else "",
            "extra": self.extra.hex() if self.extra else "",
        }
