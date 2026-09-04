"""Tests for cloud-assisted onboarding additions to cremalink.clients.cloud.Client.

Covers spec FR-002 (coffee-device filtering), FR-006 (LAN config discovery),
and FR-014 (bounded retry on transient failures).
"""

from __future__ import annotations

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
