"""Tests for PrimaDonna Soul ECAM610 statistics semantics."""

import pytest

from cremalink.devices.ecam610_statistics import (
    OBSERVED_UNKNOWN_IDS,
    build_ecam610_statistics_snapshot,
    get_unknown_statistic_note,
    interpret_ecam610_statistics,
)


RAW_REAL_ECAM610 = {
    100: 981155,
    101: 410,
    105: 30,
    106: 2736033,
    108: 22,
    109: 54380,
    111: 18,
    115: 4325,
    116: 1632,

    3000: 396,
    3001: 5231,
    3002: 2,
    3003: 180,
    3004: 340,
    3005: 97,
    3006: 3,
    3007: 0,
    3008: 1,
    3009: 48,
    3010: 119,
    3011: 151,
    3012: 9,
    3013: 148,
    3014: 1,
    3015: 180,
    3016: 5,
    3017: 0,
    3018: 0,
    3019: 2,
    3020: 0,

    3021: 0,
    3024: 0,
    3025: 0,
    3032: 0,
    3037: 243,
    3038: 0,
    3039: 0,
    3040: 0,
    3041: 0,
    3042: 0,
    3043: 1,
    3044: 0,
    3045: 0,
    3046: 4,

    23000: 152,
    23001: 21123,
    23002: 991,
    23003: 6,
    23004: 46857,
    23005: 705876,
    23006: 1133961,
    23007: 28495,
    23008: 28495,
    23009: 1015,

    43000: 4797,
    43005: 4898,
    43010: 5809,
    43011: 0,
    43012: 1,
    43014: 722,
    43015: 245,
    43016: 0,
}


def test_interpret_real_ecam610_statistics():
    stats = interpret_ecam610_statistics(RAW_REAL_ECAM610)

    assert stats["descale_count"] == 30
    assert stats["filter_replacements"] == 22
    assert stats["grounds_container_clean_count"] == 4325

    assert stats["total_water_l"] == pytest.approx(1368.0165)

    assert stats["total_black_beverages"] == 396
    assert stats["total_milk_coffee_beverages"] == 5231
    assert stats["total_milk_only_beverages"] == 180
    assert stats["total_milk_beverages"] == 5411
    assert stats["total_other_beverages"] == 2
    assert stats["total_beverages"] == 5809

    assert stats["total_espressos"] == 340
    assert stats["espresso"] == 97
    assert stats["coffee"] == 3
    assert stats["long_coffee"] == 0
    assert stats["doppio"] == 1
    assert stats["americano"] == 48
    assert stats["cappuccino"] == 119
    assert stats["latte_macchiato"] == 151
    assert stats["caffe_latte"] == 9
    assert stats["flat_white"] == 148
    assert stats["espresso_macchiato"] == 1
    assert stats["hot_milk"] == 180
    assert stats["cappuccino_doppio"] == 5
    assert stats["cappuccino_mix"] == 0
    assert stats["hot_water"] == 0
    assert stats["tea"] == 2
    assert stats["coffee_pot"] == 0


def test_total_beverages_falls_back_to_category_sum():
    raw = {
        3000: 396,
        3001: 5231,
        3002: 2,
        3003: 180,
    }

    stats = interpret_ecam610_statistics(raw)

    assert stats["total_milk_beverages"] == 5411
    assert stats["total_beverages"] == 5809


def test_snapshot_preserves_unknown_statistics():
    snapshot = build_ecam610_statistics_snapshot(
        RAW_REAL_ECAM610
    )

    assert snapshot["known"]["total_beverages"] == 5809

    assert snapshot["unknown"][23000] == 152
    assert snapshot["unknown"][23001] == 21123

    assert snapshot["unknown"][43000] == 4797
    assert snapshot["unknown"][43005] == 4898
    assert snapshot["unknown"][43014] == 722

    # Confirmed ID must not also be exposed as unknown.
    assert 43010 not in snapshot["unknown"]

    # Complete source data must remain losslessly available.
    assert snapshot["raw"] == RAW_REAL_ECAM610


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
    assert 43000 in OBSERVED_UNKNOWN_IDS
    assert 43005 in OBSERVED_UNKNOWN_IDS

    # Confirmed aggregate is deliberately not unknown.
    assert 43010 not in OBSERVED_UNKNOWN_IDS

    assert "Unknown" in get_unknown_statistic_note(23000)
    assert "with/without milk" in get_unknown_statistic_note(43000)


def test_unknown_statistics_are_not_guessed_as_known():
    stats = interpret_ecam610_statistics(
        {
            23000: 152,
            43000: 4797,
            43005: 4898,
            43014: 722,
        }
    )

    assert stats == {}
