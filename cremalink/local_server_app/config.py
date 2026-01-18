"""
This module defines the configuration settings for the local server application
using Pydantic's settings management.
"""
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import SettingsConfigDict, BaseSettings


class ServerSettings(BaseSettings):
    """
    Defines the application's settings, which can be loaded from environment
    variables or a .env file. This provides a centralized and type-safe way
    to configure the server's behavior.
    """
    server_settings_path: str = Field("", validation_alias="SERVER_SETTINGS_PATH", description="Path to the configuration file, with device credentials.")

    # --- Server Network Settings ---
    server_ip: str = Field("127.0.0.1", validation_alias="SERVER_IP", description="IP address for the server to bind to.")
    server_port: int = Field(10280, validation_alias="SERVER_PORT", description="Port for the server to listen on.")

    # --- Job Interval Settings ---
    nudger_poll_interval: float = Field(1.0, validation_alias="NUDGER_POLL_INTERVAL", description="Interval in seconds for the 'nudger' job to poll for command responses.")
    monitor_poll_interval: float = Field(5.0, validation_alias="MONITOR_POLL_INTERVAL", description="Interval in seconds for the monitor job to fetch device status.")
    rekey_interval_seconds: float = Field(60.0, validation_alias="REKEY_INTERVAL_SECONDS", description="Interval in seconds to perform the authentication key exchange.")

    # --- Buffer/Queue Size Settings ---
    queue_max_size: int = Field(200, validation_alias="QUEUE_MAX_SIZE", description="Maximum size of the command queue.")
    log_ring_size: int = Field(200, validation_alias="LOG_RING_SIZE", description="Maximum number of log entries to keep in the in-memory ring buffer.")

    # --- Device Registration Settings ---
    device_register_verify: bool = Field(False, validation_alias="DEVICE_REGISTER_VERIFY", description="Whether to verify SSL certificates during device registration.")
    device_register_ca_path: Optional[str] = Field(None, validation_alias="DEVICE_REGISTER_CA_PATH", description="Path to a custom CA bundle for SSL verification.")
    device_register_timeout: float = Field(10.0, validation_alias="DEVICE_REGISTER_TIMEOUT", description="Timeout in seconds for the device registration request.")
    enable_device_register: bool = Field(True, validation_alias="ENABLE_DEVICE_REGISTER", description="Feature flag to enable the device registration process.")

    # --- Job Feature Flags ---
    enable_nudger_job: bool = Field(True, validation_alias="ENABLE_NUDGER_JOB", description="Feature flag to enable the command polling job.")
    enable_monitor_job: bool = Field(True, validation_alias="ENABLE_MONITOR_JOB", description="Feature flag to enable the status monitoring job.")
    enable_rekey_job: bool = Field(True, validation_alias="ENABLE_REKEY_JOB", description="Feature flag to enable the periodic re-keying job.")

    # --- Testing / Determinism Hooks ---
    # These fields allow for injecting fixed values during tests to make
    # cryptographic operations deterministic.
    fixed_random_2: Optional[str] = Field(None, validation_alias="FIXED_RANDOM_2")
    fixed_time_2: Optional[str] = Field(None, validation_alias="FIXED_TIME_2")

    # Pydantic settings configuration
    model_config = SettingsConfigDict(
        env_file=".env",                # Load settings from a .env file.
        env_file_encoding="utf-8",
        populate_by_name=True,          # Allow population by field name in addition to alias.
        extra="ignore"                  # Ignore extra fields from the env file.
    )


@lru_cache
def get_settings() -> ServerSettings:
    """
    Provides a cached, global instance of the ServerSettings.
    Using lru_cache ensures that the settings are loaded from the environment
    only once.
    """
    return ServerSettings()
