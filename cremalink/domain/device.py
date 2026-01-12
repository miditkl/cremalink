"""
This module defines the core `Device` class, which represents a physical coffee
machine. It serves as the primary high-level interface for interacting with a
device, abstracting away the underlying transport and command details.
"""
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
    """Loads a JSON device map from the given file path."""
    if not device_map_path:
        return {}
    with open(device_map_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def _encode_command(hex_command: str) -> str:
    """
    Encodes a hexadecimal command string into the base64 format expected by the device.
    It prepends the command bytes with a current timestamp.
    """
    head = bytearray.fromhex(hex_command)
    timestamp = bytearray.fromhex(hex(int(time.time()))[2:])
    return b64encode(head + timestamp).decode("utf-8")


@dataclass
class Device:
    """
    Represents a coffee machine, providing methods to control and monitor it.

    This class holds the device's state (e.g., IP, model) and uses a `DeviceTransport`
    object to handle the actual communication. Device-specific capabilities are
    loaded from a "device map" file.

    Attributes:
        transport: The transport object responsible for communication.
        dsn: Device Serial Number.
        model: The model identifier of the device.
        nickname: A user-defined name for the device.
        ip: The local IP address of the device.
        lan_key: The key used for LAN-based authentication.
        scheme: The communication scheme (e.g., 'http', 'mqtt').
        is_online: Boolean indicating if the device is currently reachable.
        last_seen: Timestamp of the last communication.
        firmware: The device's firmware version.
        serial: The device's serial number.
        coffee_count: The total number of coffees made.
        command_map: A mapping of command aliases to their hex codes.
        property_map: A mapping of property aliases to their technical names.
        monitor_profile: Configuration for parsing monitor data.
        extra: A dictionary for any other miscellaneous data.
    """
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
        """
        Factory method to create a Device instance with a loaded device map.

        If `device_map_path` is not provided, it attempts to find one using the
        device's model.

        Args:
            transport: The communication transport to use.
            device_map_path: Optional path to the device map JSON file.
            **kwargs: Additional attributes to set on the Device instance.

        Returns:
            A configured Device instance.
        """
        if not device_map_path:
            device_map_path = device_map(cls.model) if cls.model else None
        
        map_data = _load_device_map(device_map_path)
        command_map = map_data.get("command_map", {}) if isinstance(map_data, dict) else {}
        property_map = map_data.get("property_map", {}) if isinstance(map_data, dict) else {}
        monitor_profile_data = map_data.get("monitor_profile", {}) if isinstance(map_data, dict) else {}
        monitor_profile = MonitorProfile.from_dict(monitor_profile_data)

        # If the transport supports it, pass the mappings to it.
        if hasattr(transport, "set_mappings"):
            try:
                transport.set_mappings(command_map, property_map)
            except Exception:
                pass  # Ignore if setting mappings fails

        return cls(
            transport=transport,
            command_map=command_map,
            property_map=property_map,
            monitor_profile=monitor_profile,
            **kwargs,
        )

    # --- Transport delegations ---
    def configure(self) -> None:
        """Configures the underlying transport."""
        self.transport.configure()

    def send_command(self, command: str) -> Any:
        """
        Encodes and sends a raw hex command to the device via the transport.

        Args:
            command: The hex command string to send.

        Returns:
            The response from the transport.
        """
        encoded = _encode_command(command)
        return self.transport.send_command(encoded)

    def refresh_monitor(self) -> Any:
        """Requests a refresh of the device's monitoring data."""
        return self.transport.refresh_monitor()

    def get_properties(self) -> Any:
        """Fetches all available properties from the device."""
        return self.transport.get_properties()

    def get_property_aliases(self) -> list[str]:
        """Returns a list of all available property aliases from the device map."""
        return list(self.property_map.keys())

    def get_property(self, name: str) -> Any:
        """
        Fetches a single property by its alias or technical name.

        Args:
            name: The alias or name of the property to fetch.

        Returns:
            The value of the requested property.
        """
        actual_name = self.resolve_property(name, default=name)
        return self.transport.get_property(actual_name)

    def health(self) -> Any:
        """Checks the health of the device connection."""
        return self.transport.health()

    # --- Command map helpers ---
    def do(self, drink_name: str) -> Any:
        """
        Executes a command by its friendly name (e.g., 'espresso').

        Args:
            drink_name: The name of the command to execute, as defined in the command_map.

        Returns:
            The response from the transport.

        Raises:
            ValueError: If the command name is not found in the device map.
        """
        key = drink_name.lower().strip()
        hex_command = self.command_map.get(key, {}).get("command")
        if not hex_command:
            raise ValueError(f"Command '{key}' not implemented; check device_map.")
        return self.send_command(hex_command)

    def get_commands(self) -> list[str]:
        """Returns a list of all available command names from the device map."""
        return list(self.command_map.keys())

    # --- Property map helpers ---
    def resolve_property(self, alias: str, default: Optional[str] = None) -> str:
        """
        Translates a property alias to its technical name using the property_map.

        Args:
            alias: The property alias to resolve.
            default: A default value to return if the alias is not found.

        Returns:
            The resolved technical name, or the alias/default if not found.
        """
        return self.property_map.get(alias, default or alias)

    # --- Monitor helpers ---
    def get_monitor_snapshot(self) -> MonitorSnapshot:
        """
        Retrieves the latest raw monitoring data from the transport.
        """
        return self.transport.get_monitor()

    def get_monitor(self) -> MonitorView:
        """
        Retrieves and parses monitoring data into a structured, human-readable view.

        Returns:
            A `MonitorView` instance containing parsed status information.
        """
        snapshot = self.get_monitor_snapshot()
        return MonitorView(snapshot=snapshot, profile=self.monitor_profile)

    def get_monitor_frame(self) -> Optional[MonitorFrame]:
        """
        Decodes the raw monitor data into a `MonitorFrame` for low-level analysis.

        Returns:
            A `MonitorFrame` if decoding is successful, otherwise None.
        """
        snapshot = self.get_monitor_snapshot()
        if not snapshot.raw_b64:
            return None
        try:
            return MonitorFrame.from_b64(snapshot.raw_b64)
        except Exception:
            return None
