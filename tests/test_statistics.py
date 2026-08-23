"""Tests for the ECAM A2 statistics protocol."""

import pytest

from cremalink.parsing.statistics import (
    build_statistics_request,
    parse_statistics_response,
)


def test_build_statistics_request_100_count_10():
    assert (
        build_statistics_request(100, 10).hex()
        == "0d08a20f00640a2397"
    )


def test_build_statistics_request_3000_count_10():
    assert (
        build_statistics_request(3000, 10).hex()
        == "0d08a20f0bb80a832c"
    )


def test_parse_real_ecam610_maintenance_packet():
    packet = bytes.fromhex(
        "d041a20f"
        "0064000ef8a3"
        "00650000019a"
        "00690000001e"
        "006a0029bfa1"
        "006c00000016"
        "006d0000d46c"
        "006f00000012"
        "0073000010e5"
        "007400000660"
        "0bb80000018c"
        "d572"
    )

    stats = parse_statistics_response(packet)

    assert stats == {
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
    }


def test_parse_real_ecam610_beverage_packet():
    packet = bytes.fromhex(
        "d041a20f"
        "0bb80000018c"
        "0bb90000146f"
        "0bba00000002"
        "0bbb000000b4"
        "0bbc00000154"
        "0bbd00000061"
        "0bbe00000003"
        "0bbf00000000"
        "0bc000000001"
        "0bc100000030"
        "100d"
    )

    stats = parse_statistics_response(packet)

    assert stats[3000] == 396
    assert stats[3001] == 5231
    assert stats[3002] == 2
    assert stats[3003] == 180
    assert stats[3004] == 340
    assert stats[3005] == 97
    assert stats[3006] == 3
    assert stats[3007] == 0
    assert stats[3008] == 1
    assert stats[3009] == 48


def test_statistics_ids_may_skip():
    packet = bytes.fromhex(
        "d017a20f"
        "a806000002d2"
        "a807000000f5"
        "a80800000000"
        "8d1b"
    )

    assert parse_statistics_response(packet) == {
        43014: 722,
        43015: 245,
        43016: 0,
    }


def test_bad_crc_is_rejected():
    packet = bytearray(
        bytes.fromhex("d00ba20f00690000001e0000")
    )

    with pytest.raises(ValueError, match="CRC"):
        parse_statistics_response(bytes(packet))


def test_statistics_request_rejects_more_than_machine_limit():
    with pytest.raises(ValueError, match="between 1 and 10"):
        build_statistics_request(100, 11)
