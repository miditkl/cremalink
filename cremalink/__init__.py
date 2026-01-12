"""
Cremalink: A Python library for interacting with De'Longhi coffee machines.

This top-level package exposes the primary user-facing classes and functions
for easy access, including the main `Client`, the `Device` model, and factory
functions for creating device instances.
"""
from cremalink.clients.cloud import Client
from cremalink.domain import Device, create_cloud_device, create_local_device
from cremalink.local_server_app import create_app, ServerSettings
from cremalink.local_server import LocalServer
from cremalink.devices import device_map
from importlib.metadata import PackageNotFoundError, version

__all__ = [
    "Client",
    "Device",
    "create_local_device",
    "create_cloud_device",
    "LocalServer",
    "create_app",
    "ServerSettings",
    "device_map",
]

try:
    __name__ = "cremalink"
    # Retrieve the package version from installed metadata.
    __version__ = version(__name__)
except PackageNotFoundError:
    # If the package is not installed (e.g., running from source),
    # fall back to a default version.
    __version__ = "0.0.0"
