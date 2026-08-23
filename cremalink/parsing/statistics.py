"""De'Longhi ECAM A2 statistics protocol helpers."""

from __future__ import annotations

from binascii import crc_hqx


STATISTICS_COMMAND = 0xA2
CRC_INITIAL = 0x1D0F
MAX_STATISTICS_COUNT = 10


def build_statistics_request(start_id: int, count: int) -> bytes:
    """Build an ECAM 0xA2 statistics request.

    The machine returns up to ``count`` existing statistic parameters
    beginning at the first available parameter >= ``start_id``.
    """

    if not 0 <= start_id <= 0xFFFF:
        raise ValueError("start_id must fit into uint16")

    if not 1 <= count <= MAX_STATISTICS_COUNT:
        raise ValueError(
            f"count must be between 1 and {MAX_STATISTICS_COUNT}"
        )

    payload = bytes(
        [
            0x0D,
            0x08,
            STATISTICS_COMMAND,
            0x0F,
            (start_id >> 8) & 0xFF,
            start_id & 0xFF,
            count,
        ]
    )

    crc = crc_hqx(payload, CRC_INITIAL)
    return payload + crc.to_bytes(2, "big")


def parse_statistics_response(packet: bytes) -> dict[int, int]:
    """Parse an ECAM 0xA2 response.

    ``packet`` must contain the native ECAM frame only. If the frame came
    from Ayla ``data_response``, strip the four-byte cloud timestamp first.

    Layout:

        D0 LEN A2 0F
        FIRST_ID_H FIRST_ID_L FIRST_VALUE_4B
        [ID_2B VALUE_4B] ...
        CRC_2B
    """

    if len(packet) < 12:
        raise ValueError("statistics response too short")

    if packet[0] != 0xD0:
        raise ValueError("not an ECAM response")

    if packet[2] != STATISTICS_COMMAND:
        raise ValueError("not an A2 statistics response")

    expected_crc = int.from_bytes(packet[-2:], "big")
    actual_crc = crc_hqx(packet[:-2], CRC_INITIAL)

    if actual_crc != expected_crc:
        raise ValueError(
            f"invalid statistics CRC: "
            f"expected 0x{expected_crc:04x}, calculated 0x{actual_crc:04x}"
        )

    statistics: dict[int, int] = {}

    first_id = int.from_bytes(packet[4:6], "big")
    first_value = int.from_bytes(packet[6:10], "big")
    statistics[first_id] = first_value

    pos = 10
    end = len(packet) - 2

    while pos + 6 <= end:
        parameter_id = int.from_bytes(packet[pos : pos + 2], "big")
        value = int.from_bytes(packet[pos + 2 : pos + 6], "big")
        statistics[parameter_id] = value
        pos += 6

    if pos != end:
        raise ValueError("malformed statistics response payload")

    return statistics
