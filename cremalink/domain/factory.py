"""
This module provides factory functions for creating `Device` instances.

These factories simplify the process of instantiating a `Device` by handling
the setup of the appropriate communication transport (`LocalTransport` or
`CloudTransport`) and the subsequent creation of the `Device` object itself.
"""
from __future__ import annotations

from typing import Optional

from cremalink.domain.device import Device
from cremalink.transports.cloud.transport import CloudTransport
from cremalink.transports.local.transport import LocalTransport


def create_local_device(
    dsn: str,
    lan_key: str,
    device_ip: Optional[str],
    server_host: str,
    server_port: int = 10280,
    device_scheme: str = "http",
    auto_configure: bool = True,
    device_map_path: Optional[str] = None,
) -> Device:
    """
    Creates a `Device` instance configured for local network communication.

    This factory sets up a `LocalTransport` which requires details about the
    local network environment, including the device's IP and the local server's
    address.

    Args:
        dsn: The Device Serial Number.
        lan_key: The key for authenticating on the local network.
        device_ip: The IP address of the coffee machine.
        server_host: The hostname or IP address of the local proxy server.
        server_port: The port of the local proxy server.
        device_scheme: The communication protocol to use with the device (e.g., 'http').
        auto_configure: If True, the transport will be configured automatically.
        device_map_path: Optional path to a device-specific command map file.

    Returns:
        A `Device` instance configured with a `LocalTransport`.
    """
    transport = LocalTransport(
        dsn=dsn,
        lan_key=lan_key,
        device_ip=device_ip,
        server_host=server_host,
        server_port=server_port,
        device_scheme=device_scheme,
        auto_configure=auto_configure,
    )
    # After transport initialization, some device attributes might be populated.
    # We pass these to the Device constructor.
    return Device.from_map(
        transport=transport,
        device_map_path=device_map_path,
        dsn=dsn,
        ip=device_ip,
        lan_key=lan_key,
        scheme=device_scheme,
    )


def create_cloud_device(
    dsn: str,
    access_token: str,
    device_map_path: Optional[str] = None,
) -> Device:
    """
    Creates a `Device` instance configured for cloud-based communication.

    This factory sets up a `CloudTransport`, which communicates with the device
    via the manufacturer's cloud services, requiring an access token.

    Args:
        dsn: The Device Serial Number.
        access_token: The authentication token for the cloud service.
        device_map_path: Optional path to a device-specific command map file.

    Returns:
        A `Device` instance configured with a `CloudTransport`.
    """
    transport = CloudTransport(dsn=dsn, access_token=access_token, device_map_path=device_map_path)
    # After transport initialization, some device attributes might be populated.
    # We pass these to the Device constructor.
    return Device.from_map(
        transport=transport,
        device_map_path=device_map_path,
        dsn=dsn,
        model=getattr(transport, "model", None),
        ip=getattr(transport, "ip", None),
        lan_key=getattr(transport, "lan_key", None),
        is_online=getattr(transport, "is_online", None),
    )
