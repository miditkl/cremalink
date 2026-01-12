"""
This package contains the transport implementation for communicating with
devices over the local network (LAN).

It exposes the `LocalTransport` class as the main entry point.
"""
from cremalink.transports.local.transport import LocalTransport

__all__ = ["LocalTransport"]
