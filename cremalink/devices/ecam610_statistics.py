"""Semantic interpretation of ECAM610 / PrimaDonna Soul A2 statistics.

The raw A2 table contains both understood and still-unidentified statistics.

Policy:
- confirmed IDs get stable semantic names;
- derived values are calculated only where verified against real hardware;
- every unrecognised ID is preserved unchanged in ``unknown``;
- the complete original table is always available as ``raw``;
- unknown IDs are never guessed from values alone.

Hardware basis:
PrimaDonna Soul ECAM610.75.MB.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


# ---------------------------------------------------------------------------
# Confirmed statistics
# ---------------------------------------------------------------------------

DIRECT_STATISTICS: dict[int, str] = {
    # Maintenance
    105: "descale_count",
    108: "filter_replacements",
    115: "grounds_container_clean_count",

    # Top-level beverage categories
    3000: "total_black_beverages",
    3001: "total_milk_coffee_beverages",
    3002: "total_other_beverages",
    3003: "total_milk_only_beverages",

    # Aggregate / individual beverages
    3004: "total_espressos",
    3005: "espresso",
    3006: "coffee",
    3007: "long_coffee",
    3008: "doppio",
    3009: "americano",
    3010: "cappuccino",
    3011: "latte_macchiato",
    3012: "caffe_latte",
    3013: "flat_white",
    3014: "espresso_macchiato",
    3015: "hot_milk",
    3016: "cappuccino_doppio",
    3017: "cappuccino_mix",
    3018: "hot_water",
    3019: "tea",
    3020: "coffee_pot",

    # Hardware-verified PrimaDonna Soul beverages / aggregates
    3037: "espresso_soul",
    3046: "over_ice",
    43000: "custom_milk_coffee_beverages",

    # Confirmed aggregate:
    #
    #   3000 + 3001 + 3002 + 3003 == 43010
    #
    # Real ECAM610.75 observation:
    #   396 + 5231 + 2 + 180 = 5809
    #   ID 43010             = 5809
    43010: "total_beverages",
}


# ID 106 is handled separately because it requires conversion to litres.
KNOWN_STATISTIC_IDS: frozenset[int] = frozenset(
    set(DIRECT_STATISTICS) | {106}
)


# ---------------------------------------------------------------------------
# Observed but not yet understood
# ---------------------------------------------------------------------------

# These IDs were observed on a real ECAM610.75.MB and deliberately remain
# unmapped until controlled before/after hardware tests identify them.
#
# This is documentation, not an exhaustive whitelist. Any future unknown ID
# is automatically retained by build_ecam610_statistics_snapshot().
OBSERVED_UNKNOWN_IDS: frozenset[int] = frozenset(
    {
        100,
        101,
        109,
        111,
        116,

        3021,
        3024,
        3025,
        3032,
        3038,
        3039,
        3040,
        3041,
        3042,
        3043,
        3044,
        3045,

        23000,
        23001,
        23002,
        23003,
        23004,
        23005,
        23006,
        23007,
        23008,
        23009,

        43005,
        43011,
        43012,
        43014,
        43015,
        43016,
    }
)


UNKNOWN_STATISTIC_NOTES: dict[int, str] = {
    100: "Unknown ECAM lifetime statistic",
    101: "Unknown ECAM lifetime statistic",
    109: "Unknown maintenance/lifetime statistic",
    111: (
        "Unknown on ECAM610.75. Other reverse-engineering work assigns "
        "different meanings on other firmware; do not assume equivalence."
    ),
    116: "Unknown maintenance/lifetime statistic",

    3021: "Unknown beverage-related statistic",
    3024: "Unknown beverage-related statistic",
    3025: "Unknown beverage-related statistic",
    3032: "Unknown beverage-related statistic",
    3038: "Unknown beverage/bean-system-related statistic",
    3039: "Unknown beverage/bean-system-related statistic",
    3040: "Unknown beverage/bean-system-related statistic",
    3041: "Unknown beverage/bean-system-related statistic",
    3042: "Unknown beverage-related statistic",
    3043: "Unknown beverage-related statistic",
    3044: "Unknown beverage-related statistic",
    3045: "Unknown beverage-related statistic",
    23000: "Unknown internal/lifetime statistic",
    23001: "Unknown internal/lifetime statistic",
    23002: "Unknown internal/lifetime statistic",
    23003: "Unknown internal/lifetime statistic",
    23004: "Unknown internal/lifetime statistic",
    23005: "Unknown internal/lifetime statistic",
    23006: "Unknown internal/lifetime statistic",
    23007: "Unknown internal/lifetime statistic",
    23008: "Unknown internal/lifetime statistic",
    23009: "Unknown internal/lifetime statistic",

    43005: (
        "Unknown aggregate-like statistic. Do not label as with/without milk "
        "without a controlled hardware delta test."
    ),
    43011: "Unknown aggregate/configuration statistic",
    43012: "Unknown aggregate/configuration statistic",
    43014: "Unknown aggregate statistic",
    43015: "Unknown aggregate statistic",
    43016: "Unknown aggregate statistic",
}


def interpret_ecam610_statistics(
    raw: Mapping[int, int],
) -> dict[str, Any]:
    """Convert confirmed raw ECAM610 A2 values to semantic statistics.

    Unknown IDs are intentionally not returned by this function. Use
    build_ecam610_statistics_snapshot() when unknown/raw values must also
    be retained.
    """

    result: dict[str, Any] = {}

    for statistic_id, name in DIRECT_STATISTICS.items():
        if statistic_id in raw:
            result[name] = int(raw[statistic_id])

    # ID 106 = lifetime water quantity.
    #
    # Real hardware:
    #   2,736,033 / 2000 = 1368.0165 litres
    if 106 in raw:
        result["total_water_l"] = int(raw[106]) / 2000.0

    # PrimaDonna Soul display statistic "with milk":
    #
    # ID 3001 + ID 3003
    #
    # Real hardware:
    #   5231 + 180 = 5411
    if 3001 in raw and 3003 in raw:
        result["total_milk_beverages"] = (
            int(raw[3001]) + int(raw[3003])
        )

    # Prefer the machine's aggregate ID 43010.
    # Fall back to the four top-level categories when it is absent.
    if "total_beverages" not in result:
        category_ids = (3000, 3001, 3002, 3003)

        if all(pid in raw for pid in category_ids):
            result["total_beverages"] = sum(
                int(raw[pid]) for pid in category_ids
            )

    return result


def build_ecam610_statistics_snapshot(
    raw: Mapping[int, int],
) -> dict[str, Any]:
    """Return known, unknown and complete raw ECAM610 statistics.

    Structure:

        {
            "known": {...},
            "unknown": {
                23000: 152,
                43000: 4797,
                ...
            },
            "raw": {...},
        }

    Every raw ID without confirmed semantics is retained in ``unknown``.
    """

    normalized_raw = {
        int(statistic_id): int(value)
        for statistic_id, value in raw.items()
    }

    known = interpret_ecam610_statistics(normalized_raw)

    unknown = {
        statistic_id: value
        for statistic_id, value in normalized_raw.items()
        if statistic_id not in KNOWN_STATISTIC_IDS
    }

    return {
        "known": known,
        "unknown": unknown,
        "raw": normalized_raw,
    }


def get_unknown_statistic_note(statistic_id: int) -> str:
    """Return documentation for an unidentified A2 statistic."""

    return UNKNOWN_STATISTIC_NOTES.get(
        statistic_id,
        "Unknown ECAM A2 statistic; preserved for future reverse engineering.",
    )
