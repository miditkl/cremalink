"""Automatic device-model detection for cloud-assisted onboarding.

Ported precedence order from ``delonghi_coffee``'s
``coordinator._detect_contentstack_pattern`` (constitution Principle IV),
but resolving to one of `cremalink`'s own existing ``device_map()`` ids
(e.g. ``ECAM452``, ``ECAM610``, ``ECAM612``) instead of ContentStack
ECAM-family strings (constitution Principle II).

Precedence (first match wins), per spec FR-004:
    1. Plaintext model pattern parsed from the raw serial number.
    2. Decoded binary-encoded serial number, mapped via a SKU lookup table.
    3. Model/product-code metadata already present in the cloud device
       listing.
    4. A static OEM-identifier-to-device-map table.

``detect_model_id()`` MUST NOT guess: if no tier matches, it returns
``None`` so the caller can fall back to the in-flow manual device-map
picker (spec FR-005) rather than ever auto-applying a wrong/default map.
"""

from __future__ import annotations

import base64
import binascii
import re
from datetime import date
from typing import Any

from cremalink.devices import get_device_maps

# SKU (decoded from the binary serial envelope) -> device_map() id.
#
# "217055" confirmed as PrimaDonna Soul (ECAM610.75): the same SKU is
# documented in delonghi_coffee's SKU_TO_ECAM_PATTERN (-> "ECAM61075", from
# confirmed hardware in issue #10) and a real-world sample decoded during
# this feature's implementation (base64
# "0BuhDwDNMjE3MDU1WloyNTA3MDEzMDEzNAD9pg==" -> SKU 217055, execution ZZ,
# 2025-07-01) from the actual owner of this exact machine. Routed to the
# dedicated `ECAM610` device map (seeded from `ECAM612.json`, which shares
# the same `espresso_soul` command but is a distinct model) pending further
# reverse-engineering of ECAM610-specific commands.
SKU_TO_DEVICE_MAP: dict[str, str] = {
    "217055": "ECAM610",
    "217100": "ECAM612",
}

# OEM identifier -> device_map() id, from delonghi_coffee's confirmed
# OEM_TO_APP_MODEL. "DL-pd-soul" is the earlier PrimaDonna Soul firmware and
# maps to `ECAM612`; "DL-millcore" is the later-firmware variant of the same
# physical machine confirmed on the owner's own hardware and maps to the
# dedicated `ECAM610` device map being reverse-engineered for this feature.
OEM_TO_DEVICE_MAP: dict[str, str] = {
    "DL-pd-soul": "ECAM612",
    "DL-millcore": "ECAM610",
    "DL-striker-cb": "ECAM452"
}

_PLAINTEXT_MODEL_RE = re.compile(r"ECAM\d+", re.IGNORECASE)

_BINARY_SERIAL_HEADER_LEN = 6
_BINARY_SERIAL_PAYLOAD_LEN = 19
_BINARY_SERIAL_TRAILER_LEN = 3
_BINARY_SERIAL_FRAME_LEN = (
    _BINARY_SERIAL_HEADER_LEN + _BINARY_SERIAL_PAYLOAD_LEN + _BINARY_SERIAL_TRAILER_LEN
)
_BINARY_SERIAL_RE = re.compile(rb"(\d{6}[A-Z0-9]{2}\d{6}[A-Z0-9]\d{4})")


def _parse_serial(raw_serial: str) -> dict[str, Any] | None:
    """Parse a raw serial number into plaintext or decoded-binary form.

    Ported (trimmed) from delonghi_coffee's ``DeLonghiApi.parse_serial_number``.
    Returns ``None`` for empty input.
    """
    if not raw_serial:
        return None

    binary = _try_decode_binary_serial(raw_serial)
    if binary is not None:
        return binary

    return {"raw": raw_serial, "format": "plaintext"}


def _try_decode_binary_serial(value: str) -> dict[str, Any] | None:
    """Attempt to decode a base64-framed binary serial envelope.

    Returns the structured dict on success, ``None`` if not a well-formed
    binary envelope (caller falls back to plaintext).
    """
    if len(value) < 28 or not re.fullmatch(r"[A-Za-z0-9+/]+={0,2}", value):
        return None
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error):
        return None

    if len(decoded) < _BINARY_SERIAL_FRAME_LEN:
        return None
    payload_slice = decoded[_BINARY_SERIAL_HEADER_LEN:-_BINARY_SERIAL_TRAILER_LEN]
    match = _BINARY_SERIAL_RE.search(payload_slice)
    if match is None:
        return None

    payload = match.group(1).decode("ascii")
    sku = payload[0:6]
    year_suffix = payload[8:10]
    month = payload[10:12]
    day = payload[12:14]

    try:
        year = 2000 + int(year_suffix)
        date(year, int(month), int(day))  # reject calendrically impossible dates
    except ValueError:
        return None

    return {"raw": value, "format": "binary", "sku": sku}


def detect_model_id(
    raw_serial: str | None,
    cloud_metadata: dict[str, Any] | None,
    oem_model: str | None,
) -> str | None:
    """Resolve a discovered device to an existing `cremalink` device-map id.

    Args:
        raw_serial: The device's raw serial number string, if known.
        cloud_metadata: Additional cloud-reported fields (e.g.
            ``product_name``, ``model``), if any.
        oem_model: The Ayla ``oem_model``/``model`` identifier, if known.

    Returns:
        A valid `cremalink` device-map id, or ``None`` if no detection tier
        yielded a recognized model. Never returns a guessed or default id.
    """
    known_maps = set(get_device_maps())

    # Tier 1 & 2: raw serial number (plaintext pattern, then binary SKU).
    parsed = _parse_serial(raw_serial) if raw_serial else None
    if parsed is not None:
        if parsed["format"] == "plaintext":
            match = _PLAINTEXT_MODEL_RE.search(parsed["raw"])
            if match:
                candidate = match.group(0).upper()
                if candidate in known_maps:
                    return candidate
        elif parsed["format"] == "binary":
            candidate = SKU_TO_DEVICE_MAP.get(parsed["sku"])
            if candidate and candidate in known_maps:
                return candidate

    # Tier 3: cloud metadata fields (product/model code).
    if cloud_metadata:
        for field in ("model", "product_code", "product_name"):
            value = cloud_metadata.get(field)
            if isinstance(value, str):
                cleaned = value.replace(".", "")
                match = _PLAINTEXT_MODEL_RE.search(cleaned)
                if match:
                    candidate = match.group(0).upper()
                    if candidate in known_maps:
                        return candidate

    # Tier 4: static OEM-identifier table.
    if oem_model:
        candidate = OEM_TO_DEVICE_MAP.get(oem_model)
        if candidate and candidate in known_maps:
            return candidate

    return None
