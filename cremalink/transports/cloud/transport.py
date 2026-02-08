"""
This module provides the `CloudTransport` class, which handles communication
with a coffee machine via the manufacturer's cloud API (Ayla Networks).
"""
from __future__ import annotations

import time
from typing import Any, Optional

import requests

from cremalink.parsing.monitor.decode import build_monitor_snapshot
from cremalink.transports.base import DeviceTransport
from cremalink.resources import load_api_config

API_USER_AGENT = "datatransport/3.1.2 android/"
TOKEN_USER_AGENT = "DeLonghiComfort/3 CFNetwork/1568.300.101 Darwin/24.2.0"


class CloudTransport(DeviceTransport):
    """
    A transport for communicating with a device via the cloud API.

    This transport interacts directly with the Ayla cloud service endpoints,
    using a short-lived access token for authentication. Upon initialization,
    it fetches key device metadata from the cloud and stores it.
    """

    def __init__(self, dsn: str, access_token: str, device_map_path: Optional[str] = None) -> None:
        """
        Initializes the CloudTransport.

        Args:
            dsn: The Device Serial Number.
            access_token: A valid OAuth access token for the cloud API.
            device_map_path: Optional path to a device-specific command map file.
        """
        self.api_conf = load_api_config()
        self.gigya_api = self.api_conf.get("GIGYA")
        self.ayla_api = self.api_conf.get("AYLA")

        self.dsn = dsn
        self.access_token = access_token
        self.device_map_path = device_map_path
        self.command_map: dict[str, Any] = {}
        self.property_map: dict[str, Any] = {}

        # Fetch device metadata from the cloud immediately upon initialization.
        device = self._get(".json").get("device", {})
        self.id = device.get("key")  # The Ayla internal device ID
        self.model = device.get("model")
        self.is_lan_enabled = device.get("lan_enabled", False)
        self.type = device.get("type")
        self.is_online = device.get("connection_status", False) == "Online"
        self.ip = device.get("lan_ip")

        # Fetch LAN key, which might be needed for other operations.
        try:
            lan = self._get("/lan.json") or {}
            self.lan_key = lan.get("lanip", {}).get("lanip_key")
        except requests.HTTPError:
            self.lan_key = None

    def configure(self) -> None:
        """Configuration is handled during __init__, so this is a no-op."""
        return None

    # ---- helpers ----
    def _get(self, path: str) -> dict:
        """Helper for making authenticated GET requests using the device DSN."""
        response = requests.get(
            url=f"{self.ayla_api.get('API_URL')}/dsns/{self.dsn}{path}",
            headers={
                "User-Agent": API_USER_AGENT,
                "Authorization": f"auth_token {self.access_token}",
                "Accept": "application/json",
            },
        )
        response.raise_for_status()
        return response.json()

    def _get_by_id(self, path: str) -> dict:
        """Helper for making authenticated GET requests using the internal device ID."""
        response = requests.get(
            url=f"{self.ayla_api.get('API_URL')}/devices/{self.id}{path}",
            headers={
                "User-Agent": API_USER_AGENT,
                "Authorization": f"auth_token {self.access_token}",
                "Accept": "application/json",
            },
        )
        response.raise_for_status()
        return response.json()

    def _post(self, path: str, data: dict) -> dict:
        """Helper for making authenticated POST requests."""
        response = requests.post(
            url=f"{self.ayla_api.get('API_URL')}/dsns/{self.dsn}{path}",
            headers={
                "User-Agent": API_USER_AGENT,
                "Authorization": f"auth_token {self.access_token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json=data,
        )
        response.raise_for_status()
        return response.json()

    # ---- DeviceTransport Implementation ----
    def send_command(self, command: str) -> Any:
        """Sends a command to the device by creating a new 'datapoint' via the cloud API."""
        payload = {"datapoint": {"value": command}}

        return self._post(path=f"/properties/{self.property_map.get('data_request', 'data_request')}/datapoints.json", data=payload)

    def set_mappings(self, command_map: dict[str, Any], property_map: dict[str, Any]) -> None:
        """Stores the provided command and property maps on the instance."""
        self.command_map = command_map
        self.property_map = property_map

    def get_properties(self) -> Any:
        """Fetches all properties for the device from the cloud API."""
        return self._get("/properties.json")

    def get_property(self, name: str) -> Any:
        """Fetches a single, specific property by name."""
        props = self._get(f"/properties.json?names[]={name}")
        # The API returns a list, even for a single property.
        if props and isinstance(props, list):
            return props[0].get("property")
        return None

    def get_monitor(self) -> Any:
        """
        Fetches, parses, and returns the device's monitoring status.

        This works by fetching the specific 'monitor' property, extracting its
        base64 value, and then decoding it into a structured snapshot.
        """
        property_name = self.property_map.get("monitor", "d302_monitor")
        prop = self.get_property(property_name) or {}
        raw_b64 = prop.get("value")
        received_at = prop.get("updated_at")

        try:
            # Convert timestamp string to float if possible, otherwise use current time.
            received_ts = float(received_at) if received_at is not None else time.time()
        except (TypeError, ValueError):
            received_ts = time.time()
        payload = {
            "monitor": {"data": {"value": raw_b64}},
            "monitor_b64": raw_b64,
            "received_at": received_ts,
        }
        return build_monitor_snapshot(payload, source="cloud", device_id=self.dsn or self.id)

    def refresh_monitor(self) -> Any:
        """
        The cloud API does not provide a direct way to force a monitor refresh.
        This method is a no-op.
        """
        return None

    def health(self) -> Any:
        """
        Returns the device's online status as determined during initialization.
        This does not perform a live health check.
        """
        return {"online": self.is_online}
