from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from base64 import b64encode
from typing import Any, Dict, Optional

from cremalink.parsing.monitor.frame import MonitorFrame
from cremalink.parsing.monitor.model import MonitorSnapshot
from cremalink.parsing.monitor.profile import MonitorProfile
from cremalink.parsing.monitor.view import MonitorView
from cremalink.transports.base import DeviceTransport
from cremalink.devices import device_map


def _load_device_map(device_map_path: Optional[str]) -> Dict[str, Any]:
    if not device_map_path:
        return {}
    with open(device_map_path, "r") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def _encode_command(hex_command: str) -> str:
    head = bytearray.fromhex(hex_command)
    timestamp = bytearray.fromhex(hex(int(time.time()))[2:])
    return b64encode(head + timestamp).decode("utf-8")


@dataclass
class Device:
    transport: DeviceTransport
    dsn: Optional[str] = None
    model: Optional[str] = None
    nickname: Optional[str] = None
    ip: Optional[str] = None
    lan_key: Optional[str] = None
    scheme: Optional[str] = None
    is_online: Optional[bool] = None
    last_seen: Optional[str] = None
    firmware: Optional[str] = None
    serial: Optional[str] = None
    coffee_count: Optional[int] = None
    command_map: Dict[str, Any] = field(default_factory=dict)
    property_map: Dict[str, Any] = field(default_factory=dict)
    monitor_profile: MonitorProfile = field(default_factory=MonitorProfile)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_map(
        cls,
        transport: DeviceTransport,
        device_map_path: Optional[str] = None,
        **kwargs,
    ) -> "Device":
        if not device_map_path:
            device_map_path = device_map(cls.model) if cls.model else None
        map_data = _load_device_map(device_map_path)
        command_map = map_data.get("command_map", {}) if isinstance(map_data, dict) else {}
        property_map = map_data.get("property_map", {}) if isinstance(map_data, dict) else {}
        monitor_profile_data = map_data.get("monitor_profile", {}) if isinstance(map_data, dict) else {}
        monitor_profile = MonitorProfile.from_dict(monitor_profile_data)
        if hasattr(transport, "set_mappings"):
            try:
                transport.set_mappings(command_map, property_map)
            except Exception:
                pass
        return cls(
            transport=transport,
            command_map=command_map,
            property_map=property_map,
            monitor_profile=monitor_profile,
            **kwargs,
        )

    # --- Transport delegations ---
    def configure(self) -> None:
        self.transport.configure()

    def send_command(self, command: str) -> Any:
        encoded = _encode_command(command)
        return self.transport.send_command(encoded)

    def refresh_monitor(self) -> Any:
        return self.transport.refresh_monitor()

    def get_properties(self) -> Any:
        return self.transport.get_properties()

    def get_property_aliases(self) -> list[str]:
        return list(self.property_map.keys())

    def get_property(self, name: str) -> Any:
        actual_name = self.resolve_property(name, default=name)
        return self.transport.get_property(actual_name)

    def health(self) -> Any:
        return self.transport.health()

    # --- Command map helpers ---
    def do(self, drink_name: str) -> Any:
        key = drink_name.lower().strip()
        hex_command = self.command_map.get(key, {}).get("command")
        if not hex_command:
            raise ValueError(f"Command '{key}' not implemented; check device_map.")
        return self.send_command(hex_command)

    def get_commands(self):
        return list(self.command_map.keys())

    # --- Property map helpers ---
    def resolve_property(self, alias: str, default: Optional[str] = None) -> str:
        return self.property_map.get(alias, default or alias)

    # --- Monitor helpers ---
    def get_monitor_snapshot(self) -> MonitorSnapshot:
        return self.transport.get_monitor()

    def get_monitor(self) -> MonitorView:
        snapshot = self.get_monitor_snapshot()
        return MonitorView(snapshot=snapshot, profile=self.monitor_profile)

    def get_monitor_frame(self) -> Optional[MonitorFrame]:
        snapshot = self.get_monitor_snapshot()
        if not snapshot.raw_b64:
            return None
        try:
            return MonitorFrame.from_b64(snapshot.raw_b64)
        except Exception:
            return None
