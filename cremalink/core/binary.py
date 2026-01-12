"""
This module provides binary utility functions for handling data conversions,
checksum calculations, and bitwise operations, often required for communication
with hardware devices.
"""
from __future__ import annotations

import base64
from typing import Iterable

# Polynomial for CRC-16 CCITT calculation.
CRC16_POLY = 0x1021


def crc16_ccitt(data: bytes) -> bytes:
    """
    Calculates the CRC-16 CCITT checksum for the given data.

    This implementation uses a specific initial value (0x1D0F) and polynomial (0x1021).

    Args:
        data: The input bytes to checksum.

    Returns:
        A 2-byte sequence representing the calculated CRC in big-endian format.
    """
    crc = 0x1D0F  # Initial CRC value.
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ CRC16_POLY
            else:
                crc <<= 1
    return (crc & 0xFFFF).to_bytes(2, byteorder="big")


def b64_to_cmd_hex(b64_data: str) -> str:
    """
    Decodes a base64 string, extracts a command frame, and returns it as a hex string.

    The function cleans the input base64 string, decodes it, and then uses the
    second byte of the decoded data as a length specifier to extract the
    relevant command frame.

    Args:
        b64_data: The base64 encoded data string.

    Returns:
        The extracted command frame as a hexadecimal string.
    """
    # Remove whitespace and add padding if necessary.
    cleaned = "".join(b64_data.split())
    cleaned += "=" * (-len(cleaned) % 4)

    # Decode the base64 string.
    raw = base64.b64decode(cleaned)

    # The second byte (index 1) is the length of the command frame.
    length = raw[1]
    cmd_frame = raw[: length + 1]

    # Return the command frame as a hex string.
    return cmd_frame.hex()


def get_bit(byte_value: int, bit_index: int) -> bool:
    """
    Gets the value of a specific bit in a byte.

    Args:
        byte_value: The integer representation of the byte.
        bit_index: The index of the bit to retrieve (0-7).

    Returns:
        True if the bit is 1, False if it is 0.

    Raises:
        ValueError: If bit_index is not between 0 and 7.
    """
    if not 0 <= bit_index <= 7:
        raise ValueError("bit_index must be between 0 and 7")
    return bool(byte_value & (1 << bit_index))


def safe_byte_at(data: Iterable[int] | bytes, index: int) -> int | None:
    """
    Safely retrieves a byte from a sequence or iterable at a given index.

    Args:
        data: The data to access, can be bytes or an iterable of integers.
        index: The index of the byte to retrieve.

    Returns:
        The byte as an integer if the index is valid, otherwise None.
    """
    try:
        # Convert to list to handle various iterable types and access by index.
        return list(data)[index]
    except (IndexError, TypeError):
        # Return None if index is out of bounds or type is not subscriptable.
        return None
