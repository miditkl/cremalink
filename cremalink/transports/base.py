"""
This module defines the abstract base protocol for device communication transports.
"""
from __future__ import annotations

from typing import Any, Protocol


class DeviceTransport(Protocol):
    """
    A protocol defining the standard interface for all device transports.

    A transport is responsible for the low-level details of communicating with a
    coffee machine, whether it's over a local network (HTTP) or via the cloud.
    This class uses `typing.Protocol` to allow for structural subtyping, meaning
    any class that implements these methods will be considered a valid transport.
    """

    def configure(self) -> None:
        """
        Performs any necessary setup or configuration for the transport.
        This could include authentication, connection setup, etc.
        """
        ...

    def send_command(self, command: str) -> Any:
        """
        Sends a command to the device.

        Args:
            command: The command payload to be sent.

        Returns:
            The response from the device, with the format depending on the
            transport implementation.
        """
        ...

    def set_mappings(self, command_map: dict[str, Any], property_map: dict[str, Any]) -> None:
        """
        (Optional) Provides the transport with device-specific command and property maps.

        This can be used by transports that need to perform lookups or translations.

        Args:
            command_map: A dictionary mapping command aliases to their details.
            property_map: A dictionary mapping property aliases to their details.
        """
        ...

    def get_monitor(self) -> Any:
        """
        Retrieves the current monitoring status data from the device.

        Returns:
            The raw monitoring data.
        """
        ...

    def refresh_monitor(self) -> Any:
        """
        Requests the device to send an updated monitoring status.
        """
        ...

    def get_properties(self) -> Any:
        """
        Fetches a set of properties from the device.

        Returns:
            A collection of device properties.
        """
        ...

    def get_property(self, name: str) -> Any:
        """
        Fetches a single, specific property from the device.

        Args:
            name: The name of the property to retrieve.

        Returns:
            The value of the requested property.
        """
        ...

    def health(self) -> Any:
        """
        Performs a health check to verify connectivity with the device.

        Returns:
            A status indicating the health of the connection.
        """
        ...
