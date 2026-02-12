"""
This module defines the Pydantic data models used for API request and response
validation in the local server application. These models ensure type safety
and clear contracts for the API endpoints.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ConfigureRequest(BaseModel):
    """
    Model for the `/configure` endpoint request body.
    It contains all the necessary information to establish a connection
    with a local device.
    """
    dsn: str
    device_ip: str
    lan_key: str
    device_scheme: str = Field("https", description="The protocol scheme, e.g., 'http' or 'https'.")
    monitor_property_name: str | None = None
    data_request_property_name: str | None = None


class CommandRequest(BaseModel):
    """Model for the `/command` endpoint request body."""
    command: str


class KeyExchange(BaseModel):
    """
    Represents the data payload for the key exchange process, which is
    part of the authentication handshake with the device.
    """
    random_1: str
    time_1: str | int


class KeyExchangeRequest(BaseModel):
    """Model for a key exchange request, wrapping the KeyExchange payload."""
    key_exchange: KeyExchange


class EncPayload(BaseModel):
    """A generic model for a payload that contains encrypted data (`enc`)."""
    enc: str


class CommandPollResponse(BaseModel):
    """
    Model for the response when polling for a command result from the device.
    It includes the encrypted response, a signature, and a sequence number.
    """
    enc: str
    sign: str
    seq: int


class MonitorResponse(BaseModel):
    """
    Model for the response from the `/get_monitor` endpoint.
    Includes the parsed monitor data, the raw base64 string, and a timestamp.
    """
    monitor: Dict[str, Any] | Any | None = None
    monitor_b64: Optional[str] = None
    received_at: Optional[float] = None


class PropertiesResponse(BaseModel):
    """
    Model for the response from the `/get_properties` endpoint.
    Includes the dictionary of properties and a timestamp.
    """
    properties: Dict[str, Any] = Field(default_factory=dict)
    received_at: Optional[float] = None
