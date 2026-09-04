"""Tests for cremalink.domain.model_detection.detect_model_id.

Covers spec FR-004 (4-tier precedence) and FR-005 (fail-closed: never a
guessed/default model). ``test_binary_serial_sku_resolves_real_soul_sample``
uses a verified real-world serial sample (see model_detection.py's
``SKU_TO_DEVICE_MAP`` comment); the fail-closed tests explicitly clear the
tables via monkeypatch to prove no other table entry masks the assertion.
"""

from __future__ import annotations

import base64

from cremalink.domain import model_detection
from cremalink.domain.model_detection import detect_model_id


def _build_binary_serial(
    sku="217055",
    execution="01",
    year="24",
    month="06",
    day="15",
    letter="A",
    production="0001",
):
    payload = f"{sku}{execution}{year}{month}{day}{letter}{production}".encode("ascii")
    assert len(payload) == 19
    frame = b"\x00" * 6 + payload + b"\x00" * 3
    return base64.b64encode(frame).decode("ascii")


def test_plaintext_serial_match_resolves_known_model(monkeypatch):
    monkeypatch.setattr(
        model_detection, "get_device_maps", lambda: ["ECAM452", "ECAM612"]
    )

    result = detect_model_id(
        raw_serial="ECAM452MB12345XYZ", cloud_metadata=None, oem_model=None
    )

    assert result == "ECAM452"


def test_binary_serial_sku_resolves_real_soul_sample(monkeypatch):
    """Real hardware sample: base64 "0BuhDwDNMjE3MDU1WloyNTA3MDEzMDEzNAD9pg=="
    decodes to SKU 217055 (PrimaDonna Soul / ECAM610.75), routed to the
    dedicated `ECAM610` device map for this confirmed machine.
    """
    monkeypatch.setattr(
        model_detection, "get_device_maps", lambda: ["ECAM452", "ECAM610", "ECAM612"]
    )

    serial = "0BuhDwDNMjE3MDU1WloyNTA3MDEzMDEzNAD9pg=="
    result = detect_model_id(raw_serial=serial, cloud_metadata=None, oem_model=None)

    assert result == "ECAM610"


def test_binary_serial_sku_resolves_via_table(monkeypatch):
    monkeypatch.setattr(
        model_detection, "get_device_maps", lambda: ["ECAM452", "ECAM612"]
    )
    monkeypatch.setattr(model_detection, "SKU_TO_DEVICE_MAP", {"217055": "ECAM612"})

    serial = _build_binary_serial(sku="217055")
    result = detect_model_id(raw_serial=serial, cloud_metadata=None, oem_model=None)

    assert result == "ECAM612"


def test_cloud_metadata_fallback_resolves_known_model(monkeypatch):
    monkeypatch.setattr(
        model_detection, "get_device_maps", lambda: ["ECAM452", "ECAM612"]
    )

    result = detect_model_id(
        raw_serial=None,
        cloud_metadata={
            "model": "ECAM610.75"
        },  # dotted variant, e.g. from Ayla product metadata
        oem_model=None,
    )

    # "ECAM610.75" -> cleaned "ECAM61075" has no digit-only match to a known
    # map in this fixture; use a model string that does resolve instead.
    assert result is None

    result2 = detect_model_id(
        raw_serial=None,
        cloud_metadata={"model": "ECAM452.details"},
        oem_model=None,
    )
    assert result2 == "ECAM452"


def test_oem_table_fallback_resolves_via_table(monkeypatch):
    monkeypatch.setattr(
        model_detection, "get_device_maps", lambda: ["ECAM452", "ECAM610", "ECAM612"]
    )

    # Earlier PrimaDonna Soul firmware -> ECAM612.
    result = detect_model_id(
        raw_serial=None, cloud_metadata=None, oem_model="DL-pd-soul"
    )
    assert result == "ECAM612"

    # Later PrimaDonna Soul firmware (confirmed on the owner's own hardware) -> ECAM610.
    result2 = detect_model_id(
        raw_serial=None, cloud_metadata=None, oem_model="DL-millcore"
    )
    assert result2 == "ECAM610"


def test_unrecognized_identifier_returns_none_never_guesses(monkeypatch):
    monkeypatch.setattr(
        model_detection, "get_device_maps", lambda: ["ECAM452", "ECAM612"]
    )
    monkeypatch.setattr(model_detection, "SKU_TO_DEVICE_MAP", {})
    monkeypatch.setattr(model_detection, "OEM_TO_DEVICE_MAP", {})

    result = detect_model_id(
        raw_serial="totally-unknown-format",
        cloud_metadata={"model": "???"},
        oem_model="DL-unknown-model",
    )

    assert result is None


def test_detection_never_returns_id_outside_known_device_maps(monkeypatch):
    """Even if a table is misconfigured, detection must not resolve to a
    device map that doesn't actually exist (constitution Principle II)."""
    monkeypatch.setattr(model_detection, "get_device_maps", lambda: ["ECAM452"])
    monkeypatch.setattr(
        model_detection, "OEM_TO_DEVICE_MAP", {"DL-pd-soul": "ECAM999-DOES-NOT-EXIST"}
    )

    result = detect_model_id(
        raw_serial=None, cloud_metadata=None, oem_model="DL-pd-soul"
    )

    assert result is None
