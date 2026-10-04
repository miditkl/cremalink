"""
This package contains the core implementation of the cremalink local proxy server,
which is a FastAPI application.

It exposes the main application factory `create_app` and the `ServerSettings`
class for configuration.
"""
def __getattr__(name):
    """Import on first access: the API module needs FastAPI, the `server` extra."""
    if name == "create_app":
        from cremalink.local_server_app.api import create_app

        return create_app
    if name == "ServerSettings":
        from cremalink.local_server_app.config import ServerSettings

        return ServerSettings
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = ["create_app", "ServerSettings"]
