"""
This module provides an adapter for communicating directly with the coffee
machine device on the local network. Its main purpose is to handle the
device registration process.
"""
from typing import Optional

import httpx

from cremalink.local_server_app.config import ServerSettings
from cremalink.local_server_app.state import LocalServerState


class DeviceAdapter:
    """
    Handles direct HTTP communication with the physical coffee machine.

    This class is responsible for the 'registration' step, where this local
    proxy server informs the coffee machine of its presence, telling it where
    to send data pushes.
    """

    def __init__(self, settings: ServerSettings, logger):
        """
        Initializes the DeviceAdapter.

        Args:
            settings: The application's configuration settings.
            logger: The application's logger instance.
        """
        self.settings = settings
        self.logger = logger
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """
        Provides a singleton instance of an `httpx.AsyncClient`.

        The client is configured with timeout and SSL verification settings
        from the application configuration.
        """
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.settings.device_register_timeout,
                verify=self.settings.device_register_ca_path or self.settings.device_register_verify,
            )
        return self._client

    async def register_with_device(self, state: LocalServerState) -> None:
        """
        Sends a registration request to the coffee machine.

        This tells the device to send its data updates (like monitor status)
        to this server's `/local_lan` endpoint.

        Args:
            state: The current server state, containing device IP and scheme.

        Raises:
            ValueError: If the device IP is not configured in the state.
            ConnectionError: If the HTTP request to the device fails.
        """
        if not self.settings.enable_device_register:
            self.logger.info("register_skipped", extra={"details": {"reason": "disabled"}})
            return

        if not state.device_ip:
            raise ValueError("Device IP not configured")

        api_url = f"{state.device_scheme}://{state.device_ip}/local_reg.json"
        # The payload tells the device this server's IP, port, and notification endpoint.
        payload = {
            "local_reg": {
                "ip": self.settings.advertised_ip or self.settings.server_ip,
                "notify": 1,
                "port": self.settings.server_port,
                "uri": "/local_lan",
            }
        }
        client = await self._get_client()
        try:
            resp = await client.put(api_url, json=payload)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            await state.set_registered(False)
            state.log("local_reg_failed", {"error": str(exc)})
            raise ConnectionError(f"local_reg failed: {exc}") from exc
        else:
            await state.set_registered(True)
            state.log("local_reg_ok", {"device_ip": state.device_ip, "scheme": state.device_scheme})

    async def close(self) -> None:
        """Closes the underlying httpx client if it exists."""
        if self._client:
            await self._client.aclose()
            self._client = None
