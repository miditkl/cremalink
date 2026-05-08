"""
This module provides a function to load the language configuration from the
embedded `lang.json` resource file.
"""
from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any


@lru_cache
def load_lang_config() -> dict[str, Any]:
    """
    Loads the language configuration from the `lang.json` resource file.

    This function uses `importlib.resources` to access the JSON file.

    The `@lru_cache` decorator memoizes the result, so the file is only read
    and parsed once, improving performance on subsequent calls.

    Returns:
        A dictionary containing the language configuration data.
    """
    resource = resources.files("cremalink.resources").joinpath("lang.json")
    with resource.open("r", encoding="utf-8") as f:
        return json.load(f)