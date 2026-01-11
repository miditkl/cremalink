"""
This package provides high-level client interfaces for interacting with
the cremalink system.

The `Client` class from the `cloud` module is exposed as the primary
entry point for this package.
"""
from cremalink.clients.cloud import Client

__all__ = ["Client"]
