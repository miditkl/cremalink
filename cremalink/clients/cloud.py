from __future__ import annotations

import json
import os

import requests

from cremalink.domain import create_cloud_device
from cremalink.resources import load_api_config

API_USER_AGENT = "datatransport/3.1.2 android/"
TOKEN_USER_AGENT = "DeLonghiComfort/3 CFNetwork/1568.300.101 Darwin/24.2.0"


class Client:
    """
    Client for interacting with the Ayla IoT cloud platform.
    Manages authentication (access and refresh tokens) and device discovery.
    """

    def __init__(self, token_path: str):
        # Ensure the token_path points to a JSON file.
        if not token_path.endswith(".json"):
            raise ValueError("token_path must point to a .json file")

        # Load API configuration from resources.
        self.api_conf = load_api_config()
        self.gigya_api = self.api_conf.get("GIGYA")
        self.ayla_api = self.api_conf.get("AYLA")

        self.token_path = token_path
        # Retrieve or refresh the access token upon initialization.
        self.access_token = self.__get_access_token()
        # Fetch the list of devices associated with the account.
        self.devices = requests.get(
            url=f"{self.ayla_api.get('API_URL')}/devices.json",
            headers={
                "User-Agent": API_USER_AGENT,
                "Authorization": f"auth_token {self.access_token}",
                "Accept": "application/json",
            },
        ).json()

    def get_devices(self):
        """
        Retrieves a list of Device Serial Numbers (DSNs) for all registered devices.

        Returns:
            list[str]: A list of DSNs.
        """
        devices: list[str] = []
        for device in self.devices:
            devices.append(device["device"]["dsn"])
        return devices

    def get_device(self, dsn: str, device_map_path: dict | None = None):
        """
        Retrieves a specific cloud device by its DSN.

        Args:
            dsn (str): The Device Serial Number of the desired device.
            device_map_path (dict | None): Optional mapping for device properties.

        Returns:
            CloudDevice | None: An instance of CloudDevice if found, otherwise None.
        """
        for device_dsn in self.get_devices():
            if device_dsn == dsn:
                return create_cloud_device(device_dsn, self.access_token, device_map_path)
        return None

    def __get_access_token(self):
        """
        Retrieves a valid access token, refreshing it if necessary using the refresh token.
        """
        refresh_token = self.__get_refresh_token()
        # If no refresh token is found, prompt the user to provide one.
        if not refresh_token or refresh_token == "":
            self.__set_refresh_token("")
            raise ValueError(f"No refresh token found. Open {self.token_path} and add a valid refresh token.")
        response = requests.post(
            url=f"{self.ayla_api.get('OAUTH_URL')}/users/refresh_token.json",
            headers={
                "User-Agent": TOKEN_USER_AGENT,
                "Content-Type": "application/json",
            },
            json={"user": {"refresh_token": refresh_token}},
        )
        if response.status_code == 200:
            # If successful, extract new access and refresh tokens.
            data = response.json()
            new_access_token = data["access_token"]
            new_refresh_token = data["refresh_token"]
            # Update the stored refresh token.
            self.__set_refresh_token(new_refresh_token)
            return new_access_token
        else:
            # Raise an error if access token retrieval fails.
            raise ValueError(f"Failed to get access token: {response.status_code} {response.text}")

    def __get_refresh_token(self):
        """
        Reads the refresh token from the token file.

        Returns:
            str | None: The refresh token if found, otherwise None.
        """
        if os.path.exists(self.token_path):
            with open(self.token_path, "r") as f:
                data = f.read()
                f.close()
                if data:
                    token_data = json.loads(data)
                    return token_data.get("refresh_token", None)
        return None

    def __set_refresh_token(self, refresh_token: str):
        """
        Writes the provided refresh token to the token file.

        Args:
            refresh_token (str): The new refresh token to store.
        """
        with open(self.token_path, "w+") as f:
            # Read existing data to preserve other potential keys.
            data = f.read()
            token_data = json.loads(data) if data else {}
            token_data["refresh_token"] = refresh_token
            f.write(json.dumps(token_data, indent=2))
            f.close()
