"""
This module provides a function to load the API configuration from the
embedded `api_config.json` resource file.
"""
from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any


@lru_cache
def load_api_config() -> dict[str, Any]:
    """
    Loads the API configuration from the `api_config.json` resource file.

    This function uses `importlib.resources` to access the JSON file.

    The `@lru_cache` decorator memoizes the result, so the file is only read
    and parsed once, improving performance on subsequent calls.

    Returns:
        A dictionary containing the API configuration data.
    """
    # Locate the 'api_config.json' file within the 'cremalink.resources' package.
    resource = resources.files("cremalink.resources").joinpath("api_config.json")
    # Open the resource file and load its JSON content.
    with resource.open("r", encoding="utf-8") as f:
        return json.load(f)
