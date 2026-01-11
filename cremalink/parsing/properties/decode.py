"""
This module provides classes for handling and decoding device properties.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class PropertiesSnapshot:
    """
    A container for a snapshot of device properties at a specific time.

    This class holds the raw property data as received from the device,
    the timestamp of when it was received, and a dictionary for any parsed
    or processed values. It provides a helper method to easily access
    property values from the potentially nested raw data structure.

    Attributes:
        raw: The raw dictionary of properties from the device.
        received_at: The timestamp when the snapshot was taken.
        parsed: A dictionary to hold processed or parsed property values.
    """
    raw: dict[str, Any]
    received_at: Optional[datetime]
    parsed: dict[str, Any] = field(default_factory=dict)

    def get(self, name: str) -> Any:
        """
        Safely retrieves a property by its name from the raw data.

        The properties data can come in different formats. This method checks
        for the property name as a direct key and also searches within the
        nested 'property' objects that are common in the API response.

        Args:
            name: The name of the property to retrieve.

        Returns:
            The property dictionary if found, otherwise None.
        """
        # First, check if the name is a top-level key in the raw dictionary.
        if name in self.raw:
            return self.raw[name]

        # If not, iterate through the values to find a nested property object.
        # This handles the common format: `{'some_id': {'property': {'name': name, ...}}}`
        for entry in self.raw.values():
            if isinstance(entry, dict) and entry.get("property", {}).get("name") == name:
                return entry
        return None
