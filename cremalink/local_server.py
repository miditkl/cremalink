"""
This script is the main entry point for running the local proxy server.

The local server acts as an intermediary between the `cremalink` library and a
coffee machine on the local network. It exposes a simple HTTP API that the
`LocalTransport` can use, and it handles the complexities of direct device
communication, including authentication and command formatting.

This script can be run directly from the command line, for example:
`cremalink-server --ip 0.0.0.0 --port 10280`
"""
import argparse
import sys
from logging import Logger

import uvicorn

from cremalink.local_server_app import create_app, ServerSettings


class LocalServer:
    """A wrapper class that encapsulates the Uvicorn server and the web application."""

    def __init__(self, settings: ServerSettings) -> None:
        """
        Initializes the server.

        Args:
            settings: A `ServerSettings` object containing configuration like
                      host and port.
        """
        self.logger = None
        self.settings = settings
        self.app = create_app(settings=self.settings)

    def start(self) -> None:
        """Starts the Uvicorn server to serve the application."""
        uvicorn.run(
            self.app,
            host=self.settings.server_ip,
            port=self.settings.server_port,
            log_level="info"
        )


def main():
    """
    Parses command-line arguments and starts the local server.
    """
    parser = argparse.ArgumentParser(description="Start the cremalink local proxy server.")
    parser.add_argument(
        "--ip",
        type=str,
        default="0.0.0.0",
        help="IP address to bind the local server to."
    )
    parser.add_argument(
        "--port",
        type=int,
        default=10280,
        help="Port to run the local server on."
    )
    parser.add_argument(
        "--advertised_ip",
        type=str,
        default=None,
        help="IP address to advertise to the coffee machine."
    )
    parser.add_argument(
        "--settings_path",
        type=str,
        default="",
        help="Path to the configuration file, with device credentials."
    )

    # Manually handle --help to avoid argument parsing errors with unknown args.
    if "--help" in sys.argv:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()
    settings = ServerSettings(server_settings_path=args.settings_path, server_ip=args.ip, server_port=args.port, advertised_ip=args.advertised_ip)
    server = LocalServer(settings)
    server.start()


if __name__ == "__main__":
    # This allows the script to be executed directly.
    sys.exit(main())
