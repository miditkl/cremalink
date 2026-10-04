"""
Cremalink: A Python library for interacting with De'Longhi coffee machines.

This top-level package exposes the primary user-facing classes and functions
for easy access, including the main `Client`, the `Device` model, and factory
functions for creating device instances.
"""
from importlib import import_module
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

# The server entry points are imported lazily (PEP 562): they need the
# `server` extra (FastAPI/uvicorn), which a client-only install — such as the
# Home Assistant integration — neither has nor needs.
_SERVER_EXPORTS = {
    "LocalServer": "cremalink.local_server",
    "ServerSettings": "cremalink.local_server_app",
    "create_app": "cremalink.local_server_app",
}


def __getattr__(name):
    """Resolve server-side exports on first access."""
    module_path = _SERVER_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
    try:
        return getattr(import_module(module_path), name)
    except ImportError as exc:  # pragma: no cover - depends on the install
        raise ImportError(
            f"'{name}' requires the local server dependencies. "
            "Install them with: pip install 'cremalink[server]'"
        ) from exc


def __dir__():
    return sorted(__all__)


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
