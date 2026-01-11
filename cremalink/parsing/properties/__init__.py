"""
This package handles the parsing and decoding of device 'properties'.

Properties are key-value pairs that represent the static or semi-static
attributes of the coffee machine, such as configuration settings or counters.
"""
from cremalink.parsing.properties.decode import PropertiesSnapshot

__all__ = ["PropertiesSnapshot"]
