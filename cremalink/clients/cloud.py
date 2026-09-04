from __future__ import annotations

import functools
import json
import logging
import os
import time

import requests

from cremalink.domain import create_cloud_device
from cremalink.resources import load_api_config

_LOGGER = logging.getLogger(__name__)

# Bounded retry for transient cloud API failures (timeouts, 5xx) during
# discovery/LAN-lookup, ported from delonghi_coffee's RETRY_COUNT/RETRY_DELAY
# convention (constitution Principle IV; spec FR-014).
RETRY_COUNT = 3
RETRY_DELAY = 2  # seconds; linear backoff between attempts
REQUEST_TIMEOUT = (5, 15)  # (connect, read) seconds; constitution Principle VI

# OEM identifier prefixes known to denote a *non*-coffee De'Longhi appliance
# on the same Ayla/cloud platform (e.g. the Pinguino air conditioner exposes
# oem_model "DL-pac" — confirmed in delonghi_coffee's is_coffee_oem_model).
# Unknown/empty models default to True — benefit of the doubt for a genuine
# but not-yet-mapped coffee maker (mirrors delonghi_coffee; spec FR-002).
NON_COFFEE_OEM_PREFIXES: tuple[str, ...] = ("DL-pac",)


def is_coffee_device(oem_model: str | None) -> bool:
    """Return True if the OEM model string denotes a coffee machine."""
    if not oem_model:
        return True
    return not oem_model.startswith(NON_COFFEE_OEM_PREFIXES)


def _retry(func):
    """Retry decorator: bounded attempts with linear backoff on transient errors.

    Applied only to read-only discovery/LAN-lookup calls (FR-014). 4xx client
    errors other than 429 (rate limited) are not retried.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        last_err: Exception | None = None
        for attempt in range(1, RETRY_COUNT + 1):
            try:
                return func(*args, **kwargs)
            except requests.RequestException as err:
                if isinstance(err, requests.HTTPError) and err.response is not None:
                    status = err.response.status_code
                    if 400 <= status < 500 and status != 429:
                        raise
                last_err = err
                if attempt < RETRY_COUNT:
                    _LOGGER.debug(
                        "Attempt %d/%d failed for %s: %s — retrying in %ds",
                        attempt,
                        RETRY_COUNT,
                        func.__name__,
                        err,
                        RETRY_DELAY,
                    )
                    time.sleep(RETRY_DELAY)
        raise last_err

    return wrapper


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

        self.token_agent = self.api_conf["USER_AGENT"]["TOKEN"]
        self.api_agent = self.api_conf["USER_AGENT"]["API"]

        self.token_path = token_path
        # Retrieve or refresh the access token upon initialization.
        self.access_token = self.__get_access_token()
        # Fetch the list of devices associated with the account.
        self.devices = requests.get(
            url=f"{self.ayla_api.get('API_URL')}/devices.json",
            headers={
                "User-Agent": self.api_agent,
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
                return create_cloud_device(
                    device_dsn, self.access_token, device_map_path
                )
        return None

    @_retry
    def list_account_devices(self) -> list[dict]:
        """Discover coffee-machine devices on the account (cloud-assisted onboarding).

        Unlike :meth:`get_devices` (kept unchanged for backward compatibility),
        this re-fetches ``/devices.json`` and returns one enriched dict per
        *coffee-machine* device only — non-coffee appliances (e.g. a Pinguino
        A/C on the same account) are excluded, not just flagged (FR-002).

        Returns:
            list[dict]: Each with ``dsn``, ``product_name``, ``oem_model``,
            ``lan_enabled``, ``connection_status``.
        """
        resp = requests.get(
            url=f"{self.ayla_api.get('API_URL')}/devices.json",
            headers={
                "User-Agent": self.api_agent,
                "Authorization": f"auth_token {self.access_token}",
                "Accept": "application/json",
            },
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        raw_devices = [d["device"] for d in resp.json()]
        self.devices = [{"device": d} for d in raw_devices]

        discovered: list[dict] = []
        for device in raw_devices:
            oem_model = device.get("oem_model") or device.get("model")
            if not is_coffee_device(oem_model):
                continue
            discovered.append(
                {
                    "dsn": device.get("dsn"),
                    "product_name": device.get("product_name"),
                    "oem_model": oem_model,
                    "lan_enabled": bool(device.get("lan_enabled", False)),
                    "connection_status": device.get("connection_status"),
                }
            )
        return discovered

    @_retry
    def get_serial_number(self, dsn: str) -> str | None:
        """Fetch the raw ``d270_serialnumber`` property for a device.

        Used as an input to model detection (FR-004); returns ``None`` if the
        property is absent rather than raising, so callers can safely fall
        through to the next detection tier.
        """
        resp = requests.get(
            url=f"{self.ayla_api.get('API_URL')}/dsns/{dsn}/properties/d270_serialnumber.json",
            headers={
                "User-Agent": self.api_agent,
                "Authorization": f"auth_token {self.access_token}",
                "Accept": "application/json",
            },
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json().get("property", {}).get("value") or None

    @_retry
    def get_lan_config(self, dsn: str) -> dict:
        """Fetch LAN connectivity details for a device (FR-006).

        Ported from ``delonghi_coffee``'s ``api.get_lan_config`` — same Ayla
        platform, same account. Never raises just because LAN is disabled;
        returns ``lan_enabled: False`` with the other fields ``None`` instead
        (FR-008).
        """
        result: dict = {
            "lan_enabled": False,
            "lanip_key": None,
            "lan_ip": None,
            "status": None,
        }

        resp = requests.get(
            url=f"{self.ayla_api.get('API_URL')}/dsns/{dsn}.json",
            headers={
                "User-Agent": self.api_agent,
                "Authorization": f"auth_token {self.access_token}",
                "Accept": "application/json",
            },
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        device = resp.json().get("device", {})
        result["lan_enabled"] = bool(device.get("lan_enabled", False))
        result["lan_ip"] = device.get("lan_ip")
        result["status"] = device.get("connection_status")

        if result["lan_enabled"]:
            lan_resp = requests.get(
                url=f"{self.ayla_api.get('API_URL')}/devices/{dsn}/lan.json",
                headers={
                    "User-Agent": self.api_agent,
                    "Authorization": f"auth_token {self.access_token}",
                    "Accept": "application/json",
                },
                timeout=REQUEST_TIMEOUT,
            )
            if lan_resp.status_code != 404:
                lan_resp.raise_for_status()
                lanip = lan_resp.json().get("lanip", {})
                result["lanip_key"] = lanip.get("lanip_key")

            if not result["lanip_key"]:
                # Fallback endpoint — some accounts/devices expose the LAN
                # key here instead (ported from delonghi_coffee's
                # get_lan_config alternate-endpoint fallback).
                alt_resp = requests.get(
                    url=f"{self.ayla_api.get('API_URL')}/devices/{dsn}/connection_config.json",
                    headers={
                        "User-Agent": self.api_agent,
                        "Authorization": f"auth_token {self.access_token}",
                        "Accept": "application/json",
                    },
                    timeout=REQUEST_TIMEOUT,
                )
                if alt_resp.status_code != 404:
                    alt_resp.raise_for_status()
                    result["lanip_key"] = alt_resp.json().get("local_key")

        return result

    def __get_access_token(self):
        """
        Retrieves a valid access token, refreshing it if necessary using the refresh token.
        """
        refresh_token = self.__get_refresh_token()
        # If no refresh token is found, prompt the user to provide one.
        if not refresh_token or refresh_token == "":
            self.__set_refresh_token("")
            raise ValueError(
                f"No refresh token found. Open {self.token_path} and add a valid refresh token."
            )
        response = requests.post(
            url=f"{self.ayla_api.get('OAUTH_URL')}/users/refresh_token.json",
            headers={
                "User-Agent": self.token_agent,
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
            raise ValueError(
                f"Failed to get access token: {response.status_code} {response.text}"
            )

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
