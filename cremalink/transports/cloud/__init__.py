"""
This package contains the transport implementation for communicating with
devices via the cloud.

It exposes the `CloudTransport` class as the main entry point.
"""
from cremalink.transports.cloud.transport import CloudTransport

__all__ = ["CloudTransport"]
