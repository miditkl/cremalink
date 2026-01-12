"""
This package handles the parsing and decoding of the device's 'monitor' data.

The monitor data is a compact binary payload that represents the real-time
status of the coffee machine, including its current state, any active alarms,
and the progress of ongoing actions. This package provides the tools to decode
this binary data into a structured and human-readable format.
"""
from cremalink.parsing.monitor.decode import build_monitor_snapshot, decode_monitor_b64
from cremalink.parsing.monitor.frame import MonitorFrame
from cremalink.parsing.monitor.model import MonitorSnapshot
from cremalink.parsing.monitor.profile import MonitorProfile
from cremalink.parsing.monitor.view import MonitorView

__all__ = [
    "build_monitor_snapshot",
    "decode_monitor_b64",
    "MonitorSnapshot",
    "MonitorView",
    "MonitorProfile",
    "MonitorFrame"
]
