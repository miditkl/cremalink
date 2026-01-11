"""
This package contains the core implementation of the cremalink local proxy server,
which is a FastAPI application.

It exposes the main application factory `create_app` and the `ServerSettings`
class for configuration.
"""
from cremalink.local_server_app.api import create_app
from cremalink.local_server_app.config import ServerSettings


def __getattr__(name):
    if name == "create_app":
        return create_app
    if name == "ServerSettings":
        return ServerSettings
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = ["create_app", "ServerSettings"]
