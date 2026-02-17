"""
This module provides the `LocalTransport` class, which handles communication
with a coffee machine over the local network (LAN) via a proxy server.
"""
from __future__ import annotations

import json
from typing import Any, Optional
from datetime import datetime

import requests

from cremalink.parsing.monitor.decode import build_monitor_snapshot
from cremalink.parsing.properties.decode import PropertiesSnapshot
from cremalink.transports.base import DeviceTransport


class LocalTransport(DeviceTransport):
    """
    A transport for communicating with a device on the local network.

    This transport does not connect to the device directly. Instead, it sends
    requests to a local proxy server (`cremalink.local_server`), which then
    forwards them to the coffee machine. This architecture simplifies direct
    device communication and authentication.
    """

    def __init__(
        self,
        dsn: str,
        lan_key: str,
        device_ip: Optional[str],
        server_host: str = "127.0.0.1",
        server_port: int = 10280,
        device_scheme: str = "http",
        auto_configure: bool = False,
        command_map: Optional[dict[str, Any]] = None,
        property_map: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Initializes the LocalTransport.

        Args:
            dsn: The Device Serial Number.
            lan_key: The key for LAN authentication.
            device_ip: The IP address of the coffee machine.
            server_host: The hostname or IP of the local proxy server.
            server_port: The port of the local proxy server.
            device_scheme: The protocol to use for device communication (e.g., 'http').
            auto_configure: If True, automatically configures the server on init.
            command_map: A pre-loaded map of device commands.
            property_map: A pre-loaded map of device properties.
        """
        self.dsn = dsn
        self.lan_key = lan_key
        self.device_ip = device_ip
        self.device_scheme = device_scheme
        self.server_base_url = f"http://{server_host}:{server_port}"
        self._configured = False
        self.command_map = command_map or {}
        self.property_map = property_map or {}
        self._auto_configure = auto_configure
        if auto_configure:
            self.configure()

    # ---- helpers ----
    def _post_server(self, path: str, body: dict, timeout: int = 10) -> requests.Response:
        """Helper for making POST requests to the local proxy server."""
        return requests.post(
            url=f"{self.server_base_url}{path}",
            headers={"Content-Type": "application/json"},
            json=body,
            timeout=timeout,
        )

    def _get_server(self, path: str, timeout: int = 10) -> requests.Response:
        """Helper for making GET requests to the local proxy server."""
        return requests.get(f"{self.server_base_url}{path}", timeout=timeout)

    # ---- DeviceTransport Implementation ----
    def configure(self) -> None:
        """
        Configures the local proxy server with the device's connection details.
        This must be called before other methods can be used.
        """
        monitor_prop_name = self.property_map.get("monitor")
        data_request_prop_name = self.property_map.get("data_request")
        payload = {
            "dsn": self.dsn,
            "device_ip": self.device_ip,
            "lan_key": self.lan_key,
            "device_scheme": self.device_scheme,
            "monitor_property_name": monitor_prop_name,
            "data_request_property_name": data_request_prop_name
        }
        try:
            resp = self._post_server("/configure", payload)
        except requests.RequestException as exc:
            raise ConnectionError(
                f"Could not reach local server at {self.server_base_url} during configure. "
                f"Start the server (python -m cremalink.local_server) or adjust server_host/server_port. "
                f"Original error: {exc}"
            ) from exc
        if resp.status_code not in (200, 201):
            raise ValueError(f"Failed to configure server: {resp.status_code} {resp.text}")
        self._configured = True

    def send_command(self, command: str, alternative_property: str = None) -> dict[str, Any]:
        """Sends a command to the device via the local proxy server."""
        if not self._configured:
            self.configure()
        resp = self._post_server("/command", {"command": command})
        resp.raise_for_status()
        return resp.json()

    def get_properties(self) -> PropertiesSnapshot:
        """Retrieves all device properties from the local proxy server."""
        resp = self._get_server("/get_properties")
        resp.raise_for_status()
        payload = resp.json()
        received = payload.get("received_at")
        received_dt = datetime.fromtimestamp(received) if received else None
        return PropertiesSnapshot(raw=payload.get("properties", payload), received_at=received_dt)

    def get_property(self, name: str) -> Any:
        """Retrieves a single property value from the local proxy server."""
        # First, try to get it from the bulk properties snapshot
        snapshot = self.get_properties()
        value = snapshot.get(name)
        if value is None:
            # If not found, request it individually
            resp = self._get_server(f"/properties/{name}")
            resp.raise_for_status()
            return resp.json().get("value")
        return value

    def get_monitor(self) -> Any:
        """Retrieves and parses the device's monitoring data."""
        resp = self._get_server("/get_monitor")
        resp.raise_for_status()
        try:
            payload = resp.json()
        except json.JSONDecodeError as exc:
            raise ValueError(f"Failed to parse monitor payload: {resp.text}") from exc
        return build_monitor_snapshot(payload, source="local", device_id=self.dsn)

    def refresh_monitor(self) -> None:
        """Requests a refresh of the monitoring data via the local proxy server."""
        resp = self._get_server("/refresh_monitor")
        resp.raise_for_status()

    def health(self) -> str:
        """Checks the health of the local proxy server."""
        return self._get_server("/health").text

    def set_mappings(self, command_map: dict[str, Any], property_map: dict[str, Any]) -> None:
        """
        Sets the command and property maps and re-configures the server if needed.
        If the name of the monitoring property changes, the server is reconfigured.
        """
        previous_monitor = self.property_map.get("monitor")
        previous_data_request = self.property_map.get("data_request")
        self.command_map = command_map
        self.property_map = property_map
        updated_monitor = self.property_map.get("monitor")
        updated_data_request = self.property_map.get("data_request")
        if self._auto_configure and (not self._configured or previous_monitor != updated_monitor or previous_data_request != updated_data_request):
            self.configure()
