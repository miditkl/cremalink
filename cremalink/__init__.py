"""
Cremalink: A Python library for interacting with De'Longhi coffee machines.

This top-level package exposes the primary user-facing classes and functions
for easy access, including the main `Client`, the `Device` model, and factory
functions for creating device instances.
"""
from importlib.metadata import PackageNotFoundError, version

from cremalink.clients.auth import authenticate_cloud
from cremalink.clients.cloud import Client
from cremalink.devices import device_map
from cremalink.domain import (
    Device,
    create_cloud_device,
    create_local_device,
    detect_model_id,
)
from cremalink.local_server import LocalServer
from cremalink.local_server_app import ServerSettings, create_app

__all__ = [
    "Client",
    "Device",
    "LocalServer",
    "ServerSettings",
    "authenticate_cloud",
    "create_app",
    "create_cloud_device",
    "create_local_device",
    "detect_model_id",
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
