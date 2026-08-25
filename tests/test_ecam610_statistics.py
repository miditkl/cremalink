"""Tests for PrimaDonna Soul ECAM610 statistics semantics."""

import pytest

from cremalink.devices.ecam610_statistics import (
    OBSERVED_UNKNOWN_IDS,
    build_ecam610_statistics_snapshot,
    get_unknown_statistic_note,
    interpret_ecam610_statistics,
)


RAW_SYNTHETIC_ECAM610 = {
    # Maintenance
    105: 7,
    106: 24680,
    108: 3,
    115: 11,

    # Beverage categories
    3000: 12,
    3001: 34,
    3002: 5,
    3003: 6,

    # Individual beverages
    3004: 9,
    3005: 4,
    3006: 2,
    3007: 1,
    3008: 3,
    3009: 2,
    3010: 7,
    3011: 8,
    3012: 9,
    3013: 10,
    3014: 11,
    3015: 6,
    3016: 12,
    3017: 13,
    3018: 14,
    3019: 15,
    3020: 16,

    # Newly identified beverage statistics
    3037: 17,
    3046: 23,
    43000: 93,

    # Deliberately unknown statistics
    23000: 91,
    23001: 92,
    43005: 94,
    43014: 95,

    # Confirmed aggregate
    43010: 57,
}


def test_interpret_synthetic_ecam610_statistics():
    stats = interpret_ecam610_statistics(RAW_SYNTHETIC_ECAM610)

    assert stats["descale_count"] == 7
    assert stats["filter_replacements"] == 3
    assert stats["grounds_container_clean_count"] == 11

    assert stats["total_water_l"] == pytest.approx(12.34)

    assert stats["total_black_beverages"] == 12
    assert stats["total_milk_coffee_beverages"] == 34
    assert stats["total_milk_only_beverages"] == 6
    assert stats["total_milk_beverages"] == 40
    assert stats["total_other_beverages"] == 5
    assert stats["total_beverages"] == 57

    assert stats["total_espressos"] == 9
    assert stats["espresso"] == 4
    assert stats["coffee"] == 2
    assert stats["long_coffee"] == 1
    assert stats["doppio"] == 3
    assert stats["americano"] == 2
    assert stats["cappuccino"] == 7
    assert stats["latte_macchiato"] == 8
    assert stats["caffe_latte"] == 9
    assert stats["flat_white"] == 10
    assert stats["espresso_macchiato"] == 11
    assert stats["hot_milk"] == 6
    assert stats["cappuccino_doppio"] == 12
    assert stats["cappuccino_mix"] == 13
    assert stats["hot_water"] == 14
    assert stats["tea"] == 15
    assert stats["coffee_pot"] == 16
    assert stats["espresso_soul"] == 17
    assert stats["over_ice"] == 23
    assert stats["custom_milk_coffee_beverages"] == 93


def test_total_beverages_falls_back_to_category_sum():
    raw = {
        3000: 2,
        3001: 3,
        3002: 4,
        3003: 5,
    }

    stats = interpret_ecam610_statistics(raw)

    assert stats["total_milk_beverages"] == 8
    assert stats["total_beverages"] == 14


def test_snapshot_preserves_unknown_statistics():
    snapshot = build_ecam610_statistics_snapshot(
        RAW_SYNTHETIC_ECAM610
    )

    assert snapshot["known"]["total_beverages"] == 57

    assert snapshot["unknown"][23000] == 91
    assert snapshot["unknown"][23001] == 92
    assert snapshot["unknown"][43005] == 94
    assert snapshot["unknown"][43014] == 95

    # Confirmed IDs must not also be exposed as unknown.
    assert 3037 not in snapshot["unknown"]
    assert 3046 not in snapshot["unknown"]
    assert 43000 not in snapshot["unknown"]
    assert 43010 not in snapshot["unknown"]

    # Complete source data must remain losslessly available.
    assert snapshot["raw"] == RAW_SYNTHETIC_ECAM610


def test_future_unknown_id_is_preserved_automatically():
    snapshot = build_ecam610_statistics_snapshot(
        {
            3000: 10,
            65000: 123456,
        }
    )

    assert snapshot["known"]["total_black_beverages"] == 10
    assert snapshot["unknown"][65000] == 123456
    assert snapshot["raw"][65000] == 123456


def test_observed_unknown_ids_are_documented():
    assert 23000 in OBSERVED_UNKNOWN_IDS
    assert 43005 in OBSERVED_UNKNOWN_IDS

    # Identified statistics are deliberately no longer unknown.
    assert 3037 not in OBSERVED_UNKNOWN_IDS
    assert 3046 not in OBSERVED_UNKNOWN_IDS
    assert 43000 not in OBSERVED_UNKNOWN_IDS
    assert 43010 not in OBSERVED_UNKNOWN_IDS

    assert "Unknown" in get_unknown_statistic_note(23000)


def test_unknown_statistics_are_not_guessed_as_known():
    stats = interpret_ecam610_statistics(
        {
            23000: 11,
            43005: 13,
            43014: 14,
        }
    )

    assert stats == {}


def test_newly_identified_ecam610_beverage_statistics():
    """New hardware-verified beverage counters get stable semantics."""

    raw = {
        3037: 17,
        3046: 23,
        43000: 42,
    }

    snapshot = build_ecam610_statistics_snapshot(raw)

    assert snapshot["known"]["espresso_soul"] == 17
    assert snapshot["known"]["over_ice"] == 23
    assert snapshot["known"]["custom_milk_coffee_beverages"] == 42

    assert 3037 not in snapshot["unknown"]
    assert 3046 not in snapshot["unknown"]
    assert 43000 not in snapshot["unknown"]
