import base64
import datetime as dt

import pytest

from cremalink.parsing.monitor.decode import build_monitor_snapshot, decode_monitor_b64
from cremalink.parsing.monitor.extractors import extract_fields_from_b64


def test_decode_monitor_b64_success():
    raw = b"hello"
    raw_b64 = base64.b64encode(raw).decode("utf-8")
    assert decode_monitor_b64(raw_b64) == raw


def test_decode_monitor_b64_accepts_missing_padding():
    raw = b"hello"
    raw_b64 = base64.b64encode(raw).decode("utf-8").rstrip("=")

    assert decode_monitor_b64(raw_b64) == raw


def test_decode_monitor_b64_failure():
    with pytest.raises(ValueError):
        decode_monitor_b64("not-base64!!!")


def test_extract_fields_from_b64_handles_invalid():
    raw_b64 = base64.b64encode(b"\x01\x02").decode("utf-8")
    parsed, warnings, errors, frame = extract_fields_from_b64(raw_b64)
    assert errors
    assert frame is None
    assert parsed.get("raw_length") == 2


def test_build_monitor_snapshot_collects_errors():
    raw_b64 = base64.b64encode(b"\x01\x02").decode("utf-8")
    payload = {"monitor_b64": raw_b64, "received_at": dt.datetime.now(dt.UTC).timestamp()}
    snapshot = build_monitor_snapshot(payload, source="local", device_id="dsn123")
    assert snapshot.raw_b64 == raw_b64
    assert snapshot.errors
    assert snapshot.source == "local"
    assert snapshot.device_id == "dsn123"
