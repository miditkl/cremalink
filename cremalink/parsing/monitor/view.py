"""
This module provides the `MonitorView` class, which offers a high-level,
user-friendly interface for accessing data from a `MonitorSnapshot`.
"""
from __future__ import annotations

from typing import Any, Optional

from cremalink.core.binary import get_bit
from cremalink.parsing.monitor.frame import MonitorFrame
from cremalink.parsing.monitor.model import MonitorSnapshot
from cremalink.parsing.monitor.profile import MonitorProfile, PredicateDefinition


class MonitorView:
    """
    A user-friendly view of a `MonitorSnapshot`, powered by a `MonitorProfile`.

    This class acts as a wrapper around a `MonitorSnapshot`. It uses a given
    `MonitorProfile` to translate raw, low-level data (like integer codes and
    bit flags) into human-readable values (like enum names and boolean predicates).

    It provides dynamic attribute access (`__getattr__`) to resolve flags and
    predicates from the profile on the fly. For example, `view.is_on` or
    `view.has_descaling_alarm`.
    """

    def __init__(self, snapshot: MonitorSnapshot, profile: MonitorProfile | dict[str, Any] | None = None) -> None:
        """
        Initializes the MonitorView.

        Args:
            snapshot: The `MonitorSnapshot` containing the data to be viewed.
            profile: A `MonitorProfile` or a dictionary to build one from. This
                     profile dictates how the raw data is interpreted.
        """
        self.snapshot = snapshot
        # Ensure profile is always a MonitorProfile instance.
        self.profile = profile if isinstance(profile, MonitorProfile) else MonitorProfile.from_dict(profile or {})
        
        # Attempt to get or parse the low-level MonitorFrame.
        self._frame: Optional[MonitorFrame] = snapshot.frame
        if self._frame is None and snapshot.raw_b64:
            try:
                self._frame = MonitorFrame.from_b64(snapshot.raw_b64)
            except Exception:
                self._frame = None

    # --- raw accessors ---
    @property
    def raw(self) -> bytes:
        """The raw bytes of the monitor payload."""
        return self.snapshot.raw

    @property
    def raw_b64(self) -> str:
        """The base64-encoded string of the monitor payload."""
        return self.snapshot.raw_b64

    @property
    def parsed(self) -> dict[str, Any]:
        """The dictionary of initially parsed, low-level fields."""
        return self.snapshot.parsed

    @property
    def received_at(self):
        """The timestamp when the snapshot was received."""
        return self.snapshot.received_at

    # --- standard fields ---
    @property
    def status_code(self) -> Optional[int]:
        """The raw integer code for the device's main status."""
        return self._frame.status if self._frame else None

    @property
    def action_code(self) -> Optional[int]:
        """The raw integer code for the device's current action."""
        return self._frame.action if self._frame else None

    @property
    def progress_percent(self) -> Optional[int]:
        """The progress percentage (0-100) of the current action."""
        return self._frame.progress if self._frame else None

    @property
    def accessory_code(self) -> Optional[int]:
        """The raw integer code for the currently detected accessory."""
        return self._frame.accessory if self._frame else None

    # --- enum mapping ---
    def _enum_lookup(self, enum_name: str, code: Optional[int]) -> Optional[str]:
        """Looks up an enum name from a code using the profile."""
        if code is None:
            return None
        mapping = self.profile.enums.get(enum_name, {})
        # Return the string name, or the original code as a string if not found.
        return mapping.get(int(code), str(code))

    @property
    def status_name(self) -> Optional[str]:
        """The human-readable name of the device's status (e.g., 'Standby')."""
        return self._enum_lookup("status", self.status_code)

    @property
    def action_name(self) -> Optional[str]:
        """The human-readable name of the device's action (e.g., 'Brewing')."""
        return self._enum_lookup("action", self.action_code)

    @property
    def accessory_name(self) -> Optional[str]:
        """The human-readable name of the accessory (e.g., 'Milk Carafe')."""
        return self._enum_lookup("accessory", self.accessory_code)

    # --- flag/predicate helpers ---
    def _resolve_flag(self, flag_name: str) -> Optional[bool]:
        """Resolves a named boolean flag using its definition in the profile."""
        if not self._frame:
            return None
        flag_def = self.profile.flags.get(flag_name)
        if not flag_def:
            return None
        
        data_bytes = self._frame.alarms if flag_def.source == "alarms" else self._frame.switches
        if flag_def.byte >= len(data_bytes):
            return None
        
        byte_val = data_bytes[flag_def.byte]
        value = get_bit(byte_val, flag_def.bit)
        return not value if flag_def.invert else value

    def _source_value(self, source: str) -> Any:
        """Gets a raw value from the frame by its source name."""
        if not self._frame:
            return None
        return {
            "alarms": self._frame.alarms,
            "switches": self._frame.switches,
            "status": self._frame.status,
            "action": self._frame.action,
            "progress": self._frame.progress,
            "accessory": self._frame.accessory,
        }.get(source)

    def _evaluate_predicate(self, definition: PredicateDefinition) -> Optional[bool]:
        """Evaluates a named predicate using its definition in the profile."""
        try:
            if definition.uses_flag():
                flag_value = self._resolve_flag(definition.flag or "")
                if flag_value is None:
                    return None
                return flag_value if definition.kind == "flag_true" else not flag_value

            if definition.uses_bit_address():
                if not self._frame or not definition.source:
                    return None
                source_bytes = self._frame.alarms if definition.source == "alarms" else self._frame.switches
                if definition.byte is None or definition.byte >= len(source_bytes) or definition.bit is None:
                    return None
                bit_value = get_bit(source_bytes[definition.byte], definition.bit)
                return bit_value if definition.kind == "bit_set" else not bit_value

            source_val = self._source_value(definition.source) if definition.source else None
            if definition.kind == "equals":
                return source_val == definition.value
            if definition.kind == "not_equals":
                return source_val != definition.value
            if definition.kind == "in_set":
                return source_val in set(definition.values or [])
            if definition.kind == "not_in_set":
                return source_val not in set(definition.values or [])
        except Exception:
            return None
        return None

    # --- dynamic access ---
    @property
    def available_fields(self) -> list[str]:
        """A list of all available dynamic fields (flags and predicates)."""
        return self.profile.available_fields()

    @property
    def profile_summary(self) -> dict[str, Any]:
        """A summary of the loaded profile."""
        return self.profile.summary()

    def __getattr__(self, item: str) -> Any:
        """
        Dynamically resolves flags and predicates from the profile.
        This allows for accessing profile-defined fields like `view.is_on`.
        """
        if item in self.profile.flags:
            return self._resolve_flag(item)
        if item in self.profile.predicates:
            return self._evaluate_predicate(self.profile.predicates[item])
        raise AttributeError(f"{self.__class__.__name__} has no attribute '{item}'")
