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


def test_monitor_frame_accepts_missing_base64_padding(monkeypatch):
    from cremalink.parsing.monitor.frame import MonitorFrame

    # Synthetic frame bytes. Parsing internals are not under test here;
    # only that valid base64 without trailing "=" reaches the parser.
    raw = b"\xd0\x04\x00\x00\x00"
    encoded = base64.b64encode(raw).decode("ascii").rstrip("=")

    original_b64decode = base64.b64decode

    def decode_with_marker(value, *args, **kwargs):
        # The production implementation must repair padding before decoding.
        assert len(value) % 4 == 0
        return original_b64decode(value, *args, **kwargs)

    monkeypatch.setattr(
        "cremalink.parsing.monitor.frame.base64.b64decode",
        decode_with_marker,
    )

    with pytest.raises(ValueError):
        MonitorFrame.from_b64(encoded)
