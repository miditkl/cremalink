"""
This package contains static resources and configuration files for the cremalink
library, such as API keys and language mappings.

It provides helper functions to access these resources in a way that is
compatible with standard Python packaging.
"""
from cremalink.resources.api_config import load_api_config

__all__ = ["load_api_config"]
