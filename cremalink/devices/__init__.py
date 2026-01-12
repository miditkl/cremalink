"""
This module handles the discovery and loading of device definition files,
referred to as "device maps."
"""
from __future__ import annotations

import json
import pathlib
import tempfile
from pathlib import Path
from typing import Any, List
from importlib import resources


class DeviceMapNotFoundError(FileNotFoundError):
    """Custom exception raised when a specific device map cannot be found."""
    pass


def _normalize_model_id(model_id: str) -> str:
    """
    Cleans and validates the model ID string.

    Args:
        model_id: The raw model ID.

    Returns:
        A normalized model ID string.

    Raises:
        ValueError: If the model_id is empty or just whitespace.
    """
    if not model_id or not model_id.strip():
        raise ValueError("device_map(model_id) requires a non-empty model_id.")
    model_id = model_id.strip()
    # Remove .json extension if present, case-insensitively.
    if model_id.lower().endswith(".json"):
        model_id = model_id[:-5]
    return model_id


def get_device_maps() -> List[str]:
    """
    Lists all available device maps by scanning the package data.

    Returns:
        A sorted list of unique model IDs (without the .json extension).
    """
    # Access the 'cremalink.devices' package as a resource container.
    base = resources.files("cremalink.devices")
    models: List[str] = []
    for entry in base.iterdir():
        # Find all .json files in the package.
        if entry.is_file() and entry.name.lower().endswith(".json"):
            models.append(Path(entry.name).stem)
    # Return a sorted list of unique model names.
    return sorted(set(models))


def device_map(model_id: str) -> str:
    """
    Finds the absolute path to a device map file for a given model ID.

    This function handles packaged resources, extracting them to a temporary
    directory if they are not directly accessible on the filesystem.

    Args:
        model_id: The model ID of the device.

    Returns:
        The absolute path to the device map JSON file as a string.

    Raises:
        DeviceMapNotFoundError: If the map for the given model ID doesn't exist.
    """
    model_id = _normalize_model_id(model_id)
    filename = f"{model_id}.json"

    base = resources.files("cremalink.devices")
    res: pathlib.Path = base.joinpath(filename)

    if not res.exists():
        available = get_device_maps()
        raise DeviceMapNotFoundError(
            f"Device map '{model_id}' not found. Available: {available}"
        )

    try:
        # Efficiently get the file path if the resource is on the filesystem.
        with resources.as_file(res) as p:
            return str(Path(p))
    except Exception:
        # Fallback for zipped packages: copy the file to a temp location.
        cache_dir = Path(tempfile.gettempdir()) / "cremalink_device_maps"
        cache_dir.mkdir(parents=True, exist_ok=True)
        target = cache_dir / filename

        # Write the file to the temp cache and return its path.
        target.write_bytes(res.read_bytes())
        return str(target)


def load_device_map(model_id: str) -> dict[str, Any]:
    """
    Loads a device map from its JSON file into a dictionary.

    Args:
        model_id: The model ID of the device to load.

    Returns:
        A dictionary containing the device map data, or an empty dict on failure.
    """
    path = device_map(model_id)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}
