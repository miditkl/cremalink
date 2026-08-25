"""Tests for cloud-assisted onboarding additions to cremalink.clients.cloud.Client.

Covers spec FR-002 (coffee-device filtering), FR-006 (LAN config discovery),
and FR-014 (bounded retry on transient failures).
"""

from __future__ import annotations

import base64
import json

import pytest
import requests
from cremalink.clients.cloud import Client


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)


def _make_client(tmp_path, monkeypatch, raw_devices=None):
    """Construct a Client with __init__'s network calls stubbed out."""
    token_file = tmp_path / "token.json"
    token_file.write_text(json.dumps({"refresh_token": "rt"}))

    monkeypatch.setattr(
        "cremalink.clients.cloud.requests.post",
        lambda *a, **k: _FakeResponse(
            200, {"access_token": "at", "refresh_token": "rt2"}
        ),
    )
    monkeypatch.setattr(
        "cremalink.clients.cloud.requests.get",
        lambda *a, **k: _FakeResponse(
            200, [{"device": d} for d in (raw_devices or [])]
        ),
    )
    return Client(str(token_file))


def test_list_account_devices_filters_non_coffee_appliances(tmp_path, monkeypatch):
    raw_devices = [
        {
            "dsn": "AC000W1",
            "product_name": "PrimaDonna Soul",
            "oem_model": "DL-pd-soul",
            "lan_enabled": True,
        },
        {
            "dsn": "AC000W2",
            "product_name": "Pinguino",
            "oem_model": "DL-pac",
            "lan_enabled": False,
        },
    ]
    client = _make_client(tmp_path, monkeypatch, raw_devices)

    monkeypatch.setattr(
        "cremalink.clients.cloud.requests.get",
        lambda *a, **k: _FakeResponse(200, [{"device": d} for d in raw_devices]),
    )
    devices = client.list_account_devices()

    assert [d["dsn"] for d in devices] == ["AC000W1"]
    assert devices[0]["product_name"] == "PrimaDonna Soul"


def test_list_account_devices_multiple_coffee_machines(tmp_path, monkeypatch):
    raw_devices = [
        {
            "dsn": "AC000W1",
            "product_name": "PrimaDonna Soul",
            "oem_model": "DL-pd-soul",
        },
        {
            "dsn": "AC000W2",
            "product_name": "Dinamica Plus",
            "oem_model": "DL-dinamica-plus",
        },
    ]
    client = _make_client(tmp_path, monkeypatch, raw_devices)
    monkeypatch.setattr(
        "cremalink.clients.cloud.requests.get",
        lambda *a, **k: _FakeResponse(200, [{"device": d} for d in raw_devices]),
    )

    devices = client.list_account_devices()
    assert {d["dsn"] for d in devices} == {"AC000W1", "AC000W2"}


def test_get_lan_config_returns_key_and_ip_when_enabled(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch, [])

    responses = [
        _FakeResponse(
            200,
            {
                "device": {
                    "lan_enabled": True,
                    "lan_ip": "192.168.1.42",
                    "connection_status": "Online",
                }
            },
        ),
        _FakeResponse(200, {"lanip": {"lanip_key": "abc123"}}),
    ]
    monkeypatch.setattr(
        "cremalink.clients.cloud.requests.get", lambda *a, **k: responses.pop(0)
    )

    result = client.get_lan_config("AC000W1")
    assert result["lan_enabled"] is True
    assert result["lan_ip"] == "192.168.1.42"
    assert result["lanip_key"] == "abc123"


def test_get_lan_config_falls_back_to_connection_config_endpoint(tmp_path, monkeypatch):
    """Some devices don't expose lanip_key under /devices/{dsn}/lan.json's
    "lanip" key (confirmed on real hardware) — fall back to
    /devices/{dsn}/connection_config.json's "local_key" instead."""
    client = _make_client(tmp_path, monkeypatch, [])

    responses = [
        _FakeResponse(
            200,
            {
                "device": {
                    "lan_enabled": True,
                    "lan_ip": "192.168.1.42",
                    "connection_status": "Online",
                }
            },
        ),
        _FakeResponse(200, {"lanip": {}}),
        _FakeResponse(200, {"local_key": "fallback-key"}),
    ]
    monkeypatch.setattr(
        "cremalink.clients.cloud.requests.get", lambda *a, **k: responses.pop(0)
    )

    result = client.get_lan_config("AC000W1")
    assert result["lanip_key"] == "fallback-key"


def test_get_lan_config_disabled_returns_false_not_exception(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch, [])
    monkeypatch.setattr(
        "cremalink.clients.cloud.requests.get",
        lambda *a, **k: _FakeResponse(200, {"device": {"lan_enabled": False}}),
    )

    result = client.get_lan_config("AC000W1")
    assert result["lan_enabled"] is False
    assert result["lanip_key"] is None


def test_get_lan_config_retries_on_transient_failure_then_succeeds(
    tmp_path, monkeypatch
):
    client = _make_client(tmp_path, monkeypatch, [])
    monkeypatch.setattr("cremalink.clients.cloud.time.sleep", lambda *_a, **_k: None)

    calls = {"count": 0}

    def flaky_get(*_a, **_k):
        calls["count"] += 1
        if calls["count"] < 2:
            raise requests.ConnectionError("transient")
        return _FakeResponse(200, {"device": {"lan_enabled": False}})

    monkeypatch.setattr("cremalink.clients.cloud.requests.get", flaky_get)

    result = client.get_lan_config("AC000W1")
    assert result["lan_enabled"] is False
    assert calls["count"] == 2


def test_get_lan_config_raises_after_exhausting_retries(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch, [])
    monkeypatch.setattr("cremalink.clients.cloud.time.sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "cremalink.clients.cloud.requests.get",
        lambda *_a, **_k: (_ for _ in ()).throw(requests.ConnectionError("down")),
    )

    with pytest.raises(requests.ConnectionError):
        client.get_lan_config("AC000W1")


def test_get_statistics_reads_a2_response(
    tmp_path, monkeypatch
):
    client = _make_client(tmp_path, monkeypatch, [])

    fixed_time = 1787483540
    monkeypatch.setattr(
        "cremalink.clients.cloud.time.time",
        lambda: fixed_time,
    )

    posted = {}

    def fake_post(*_a, **kwargs):
        posted.update(kwargs)
        return _FakeResponse(201, {})

    # Synthetic response: only transport/correlation is tested here.
    raw_response = (
        bytes([0xD0, 0x0C, 0xA2, 0x0F])
        + (100).to_bytes(2, "big")
        + bytes(6)
        + (fixed_time + 1).to_bytes(4, "big")
    )
    cloud_response = base64.b64encode(raw_response).decode()

    monkeypatch.setattr(
        "cremalink.clients.cloud.requests.post",
        fake_post,
    )
    monkeypatch.setattr(
        "cremalink.clients.cloud.requests.get",
        lambda *_a, **_k: _FakeResponse(
            200,
            [{"datapoint": {"value": cloud_response}}],
        ),
    )
    monkeypatch.setattr(
        "cremalink.clients.cloud.parse_statistics_response",
        lambda _packet: {
            100: 11,
            105: 22,
        },
    )

    stats = client.get_statistics(
        "AC000W1",
        100,
        10,
        wait_timeout=1,
        poll_interval=0,
    )

    assert stats == {
        100: 11,
        105: 22,
    }

    sent = base64.b64decode(
        posted["json"]["datapoint"]["value"]
    )

    assert sent[:-4].hex() == "0d08a20f00640a2397"
    assert int.from_bytes(sent[-4:], "big") == fixed_time


def test_get_statistics_continues_polling_after_read_timeout(
    tmp_path, monkeypatch
):
    client = _make_client(tmp_path, monkeypatch, [])

    fixed_time = 1787483780
    monkeypatch.setattr(
        "cremalink.clients.cloud.time.time",
        lambda: fixed_time,
    )

    monkeypatch.setattr(
        "cremalink.clients.cloud.requests.post",
        lambda *_a, **_k: _FakeResponse(201, {}),
    )

    raw_response = (
        bytes([0xD0, 0x0C, 0xA2, 0x0F])
        + (100).to_bytes(2, "big")
        + bytes(6)
        + (fixed_time + 1).to_bytes(4, "big")
    )
    cloud_response = base64.b64encode(raw_response).decode()

    responses = iter([
        requests.ReadTimeout("synthetic read timeout"),
        _FakeResponse(
            200,
            [{"datapoint": {"value": cloud_response}}],
        ),
    ])

    def fake_get(*_a, **_k):
        result = next(responses)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(
        "cremalink.clients.cloud.requests.get",
        fake_get,
    )
    monkeypatch.setattr(
        "cremalink.clients.cloud.parse_statistics_response",
        lambda _packet: {100: 1},
    )

    stats = client.get_statistics(
        "AC000W1",
        start_id=100,
        count=1,
        wait_timeout=1,
        poll_interval=0,
    )

    assert stats == {100: 1}


def test_get_statistics_accepts_first_available_id_after_start(
    tmp_path, monkeypatch
):
    client = _make_client(tmp_path, monkeypatch, [])

    fixed_time = 1787483780
    monkeypatch.setattr(
        "cremalink.clients.cloud.time.time",
        lambda: fixed_time,
    )

    monkeypatch.setattr(
        "cremalink.clients.cloud.requests.post",
        lambda *_a, **_k: _FakeResponse(201, {}),
    )

    # Real-style response to a request starting at 43013:
    # 43013 does not exist, so the machine starts with 43014.
    native_response = bytes.fromhex(
        "d017a20f"
        "a806000002d2"
        "a807000000f5"
        "a80800000000"
        "8d1b"
    )

    cloud_response = base64.b64encode(
        native_response + (fixed_time + 1).to_bytes(4, "big")
    ).decode()

    monkeypatch.setattr(
        "cremalink.clients.cloud.requests.get",
        lambda *_a, **_k: _FakeResponse(
            200,
            [{"datapoint": {"value": cloud_response}}],
        ),
    )

    stats = client.get_statistics(
        "AC000W1",
        start_id=43013,
        count=10,
        wait_timeout=1,
        poll_interval=0,
    )

    assert stats == {
        43014: 722,
        43015: 245,
        43016: 0,
    }



def test_get_all_statistics_pages_across_sparse_ids(
    tmp_path, monkeypatch
):
    client = _make_client(tmp_path, monkeypatch, [])

    pages = {
        100: {
            100: 1,
            101: 2,
            105: 3,
            106: 4,
            108: 5,
            109: 6,
            111: 7,
            115: 8,
            116: 9,
            3000: 10,
        },
        3001: {
            3001: 11,
            3002: 12,
            3003: 13,
            3004: 14,
            3005: 15,
            3006: 16,
            3007: 17,
            3008: 18,
            3009: 19,
            3010: 20,
        },
        3011: {
            3011: 21,
            3012: 22,
            3013: 23,
        },
    }

    calls = []

    def fake_get_statistics(
        dsn,
        start_id=100,
        count=10,
        **_kwargs,
    ):
        calls.append((dsn, start_id, count))
        return pages[start_id]

    monkeypatch.setattr(
        client,
        "get_statistics",
        fake_get_statistics,
    )

    stats = client.get_all_statistics("AC000W1")

    assert calls == [
        ("AC000W1", 100, 10),
        ("AC000W1", 3001, 10),
        ("AC000W1", 3011, 10),
    ]

    assert len(stats) == 23
    assert stats[100] == 1
    assert stats[3000] == 10
    assert stats[3013] == 23


def test_get_all_statistics_reduces_page_size_after_timeout_and_resets_per_page(
    tmp_path, monkeypatch
):
    client = _make_client(tmp_path, monkeypatch, [])

    calls = []
    sleeps = []

    def fake_get_statistics(
        dsn,
        start_id=100,
        count=10,
        **_kwargs,
    ):
        calls.append((dsn, start_id, count))

        if start_id == 100:
            if count > 8:
                raise TimeoutError("synthetic timeout")

            return {
                100: 1,
                101: 2,
                102: 3,
                103: 4,
                104: 5,
                105: 6,
                106: 7,
                107: 8,
            }

        if start_id == 108:
            return {
                108: 9,
                110: 10,
                115: 11,
            }

        raise AssertionError(
            f"unexpected request start_id={start_id}, count={count}"
        )

    monkeypatch.setattr(
        client,
        "get_statistics",
        fake_get_statistics,
    )
    monkeypatch.setattr(
        "cremalink.clients.cloud.time.sleep",
        lambda seconds: sleeps.append(seconds),
    )

    stats = client.get_all_statistics("AC000W1")

    assert calls == [
        ("AC000W1", 100, 10),
        ("AC000W1", 100, 9),
        ("AC000W1", 100, 8),
        ("AC000W1", 108, 10),
    ]
    assert sleeps == [5, 5]
    assert stats == {
        100: 1,
        101: 2,
        102: 3,
        103: 4,
        104: 5,
        105: 6,
        106: 7,
        107: 8,
        108: 9,
        110: 10,
        115: 11,
    }


def test_get_all_statistics_rejects_invalid_page_size(
    tmp_path, monkeypatch
):
    client = _make_client(tmp_path, monkeypatch, [])

    with pytest.raises(ValueError, match="between 1 and 10"):
        client.get_all_statistics(
            "AC000W1",
            page_size=11,
        )


def test_get_all_statistics_detects_non_progressing_page(
    tmp_path, monkeypatch
):
    client = _make_client(tmp_path, monkeypatch, [])

    monkeypatch.setattr(
        client,
        "get_statistics",
        lambda *_a, **_k: {99: 1},
    )

    with pytest.raises(ValueError, match="did not advance"):
        client.get_all_statistics(
            "AC000W1",
            start_id=100,
        )



def test_get_ecam610_statistics_preserves_known_unknown_and_raw(
    tmp_path, monkeypatch
):
    client = _make_client(tmp_path, monkeypatch, [])

    raw = {
        105: 4,
        106: 24680,
        108: 3,
        115: 11,
        3000: 12,
        3001: 20,
        3002: 5,
        3003: 7,
        43000: 91,
        43005: 92,
        43010: 44,
    }

    monkeypatch.setattr(
        client,
        "get_all_statistics",
        lambda dsn: raw,
    )

    snapshot = client.get_ecam610_statistics("AC000W1")

    assert snapshot["known"]["descale_count"] == 4
    assert snapshot["known"]["filter_replacements"] == 3
    assert snapshot["known"]["grounds_container_clean_count"] == 11

    assert snapshot["known"]["total_water_l"] == pytest.approx(12.34)

    assert snapshot["known"]["total_black_beverages"] == 12
    assert snapshot["known"]["total_milk_beverages"] == 27
    assert snapshot["known"]["total_beverages"] == 44

    assert snapshot["known"]["custom_milk_coffee_beverages"] == 91

    assert snapshot["unknown"] == {
        43005: 92,
    }

    assert snapshot["raw"] == raw


def test_get_all_statistics_does_not_infer_eof_from_timeout(
    tmp_path, monkeypatch
):
    client = _make_client(tmp_path, monkeypatch, [])

    calls = []

    def fake_get_statistics(
        dsn,
        start_id=100,
        count=10,
        **kwargs,
    ):
        calls.append(
            (
                dsn,
                start_id,
                count,
                kwargs.get("wait_timeout"),
            )
        )

        if start_id == 100:
            return {
                100: 11,
                101: 12,
            }

        if start_id == 102:
            raise TimeoutError("synthetic transient A2 timeout")

        raise AssertionError(
            f"unexpected request start_id={start_id}, count={count}"
        )

    monkeypatch.setattr(
        client,
        "get_statistics",
        fake_get_statistics,
    )
    monkeypatch.setattr(
        "cremalink.clients.cloud.time.sleep",
        lambda _seconds: None,
    )

    with pytest.raises(
        TimeoutError,
        match="synthetic transient A2 timeout",
    ):
        client.get_all_statistics(
            "AC000W1",
            start_id=100,
            page_size=2,
        )


def test_get_all_statistics_reports_live_progress(
    tmp_path, monkeypatch
):
    """Full A2 reads should report page/request progress."""

    client = _make_client(tmp_path, monkeypatch, [])

    pages = {
        100: {
            100: 1,
            105: 2,
        },
        106: {
            106: 3,
        },
    }

    def fake_get_statistics(
        _dsn,
        start_id=100,
        count=10,
        **_kwargs,
    ):
        return pages[start_id]

    monkeypatch.setattr(
        client,
        "get_statistics",
        fake_get_statistics,
    )

    progress = []

    result = client.get_all_statistics(
        "AC000W1",
        start_id=100,
        page_size=2,
        progress_callback=progress.append,
    )

    assert result == {
        100: 1,
        105: 2,
        106: 3,
    }

    assert progress == [
        {
            "phase": "request",
            "page": 1,
            "start_id": 100,
            "request_count": 2,
            "collected_count": 0,
        },
        {
            "phase": "page_complete",
            "page": 1,
            "start_id": 100,
            "request_count": 2,
            "returned_count": 2,
            "last_id": 105,
            "collected_count": 2,
        },
        {
            "phase": "request",
            "page": 2,
            "start_id": 106,
            "request_count": 2,
            "collected_count": 2,
        },
        {
            "phase": "page_complete",
            "page": 2,
            "start_id": 106,
            "request_count": 2,
            "returned_count": 1,
            "last_id": 106,
            "collected_count": 3,
        },
    ]
