import asyncio
import base64

from cremalink import device_map
from cremalink.core.binary import crc16_ccitt
from cremalink.domain.device import Device
from cremalink.local_server_app.state import LocalServerState
from cremalink.parsing.monitor.decode import build_monitor_snapshot


def build_monitor_b64(
    accessory: int = 1,
    switches: bytes = bytes([0x08, 0x00]),
    alarms: bytes = bytes([0x00, 0x20, 0x00, 0x00]),
    status: int = 7,
    progress: int = 42,
    action: int = 0,
) -> str:
    contents = bytes(
        [
            accessory,
            switches[0],
            switches[1],
            alarms[0],
            alarms[1],
            status,
            action,
            progress,
            alarms[2],
            alarms[3],
            0,
            0,
            0,
        ]
    )
    request_id = 117
    answer_required = 15
    data = bytes([request_id, answer_required]) + contents
    length = len(data) + 3
    header = bytes([0xD0, length]) + data
    crc = crc16_ccitt(header[: length - 1])
    raw = header + crc + b"\x00\x00\x00\x00"
    return base64.b64encode(raw).decode("utf-8")


class StubTransport:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.mappings: dict | None = None

    def set_mappings(self, command_map, property_map):
        self.mappings = {"command_map": command_map, "property_map": property_map}

    def configure(self):
        return None

    def send_command(self, command: str):
        return command

    def get_monitor(self):
        return self.snapshot

    def refresh_monitor(self):
        return None

    def get_properties(self):
        return {}

    def get_property(self, name: str):
        return None

    def health(self):
        return {}


def test_monitor_view_and_profile_flags():
    monitor_b64 = build_monitor_b64()
    snapshot = build_monitor_snapshot({"monitor_b64": monitor_b64, "received_at": 1.0}, source="local", device_id="dsn1")
    transport = StubTransport(snapshot)
    device = Device.from_map(
        transport=transport, device_map_path=device_map("AY008ESP1"), dsn="dsn1", nickname="test"
    )

    view = device.get_monitor()
    assert view.progress_percent == 42
    assert view.status_code == 7
    assert view.status_name == "ready"
    assert view.accessory_name == "hot_water_spout"
    assert view.is_watertank_open is True
    assert view.is_waste_container_missing is True
    assert device.resolve_property("monitor") == "d302_monitor"
    assert transport.mappings["property_map"]["monitor"] == "d302_monitor"


def test_queue_monitor_uses_configured_property_name():
    class DummySettings:
        queue_max_size = 10
        log_ring_size = 10
        fixed_random_2 = None
        fixed_time_2 = None
        server_settings_path = ""

    class DummyLogger:
        def info(self, *args, **kwargs):
            return None

    async def run():
        state = LocalServerState(DummySettings(), DummyLogger())
        await state.configure(
            dsn="dsn1",
            device_ip="1.2.3.4",
            lan_key="lan-key",
            device_scheme="http",
            monitor_property_name="d302_monitor",
        )

        await state.queue_monitor()
        async with state.lock:
            queued_payload = state.command_queue[0]
        assert "d302_monitor" in queued_payload

    asyncio.run(run())


def test_monitor_profile_predicates_and_enums():
    monitor_b64 = build_monitor_b64(accessory=2, status=1, progress=5, switches=bytes([0x00, 0x00]), action=1)
    snapshot = build_monitor_snapshot({"monitor_b64": monitor_b64, "received_at": 1.0}, source="local", device_id="dsn1")
    transport = StubTransport(snapshot)
    device = Device.from_map(
        transport=transport, device_map_path=device_map("AY008ESP1"), dsn="dsn1", nickname="test"
    )
    view = device.get_monitor()

    # enums
    assert view.accessory_name == "latte_crema_hot"
    assert view.status_name == "waking_up"

    # predicates
    assert view.is_busy is True
    assert view.is_idle is False
    assert "is_busy" in view.available_fields
    assert "is_watertank_empty" in view.available_fields
