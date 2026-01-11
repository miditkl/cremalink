"""
This module provides a set of cryptographic helper functions for handling
encryption, decryption, and hashing, primarily using AES and HMAC.
"""

import base64
import hashlib
import hmac

from Crypto.Cipher import AES


def hmac_for_key_and_data(key: bytes, data: bytes) -> bytes:
    """
    Generates an HMAC-SHA256 digest for the given key and data.

    Args:
        key: The secret key for the HMAC operation.
        data: The message data to hash.

    Returns:
        The raw HMAC-SHA256 digest as bytes.
    """
    mac_hash = hmac.new(key, data, hashlib.sha256)
    return mac_hash.digest()


def pad_zero(data: bytes, block_size: int = 16) -> bytes:
    """
    Pads data with zero bytes to a multiple of the specified block size.

    Note: This padding scheme is not reversible if the original data can
    end with zero bytes.

    Args:
        data: The bytes to pad.
        block_size: The block size to align to. Defaults to 16.

    Returns:
        The zero-padded data.
    """
    padding_length = block_size - len(data) % block_size
    return data + (padding_length * b"\x00")


def unpad_zero(data: bytes) -> bytes:
    """
    Removes trailing zero-byte padding from data.

    This works by finding the first null byte and truncating the rest.

    Args:
        data: The padded bytes.

    Returns:
        The unpadded data.
    """
    # Finds the first occurrence of a null byte and slices the data up to that point.
    return data.rstrip(b"\x00")


def extract_bits(raw: bytes, start: int, end: int) -> bytearray:
    """
    Extracts a slice from the hexadecimal representation of raw bytes.

    Note: The name is a misnomer; it operates on the hex string, not raw bits.

    Args:
        raw: The input bytes.
        start: The starting index in the hex string representation.
        end: The ending index in the hex string representation.

    Returns:
        A bytearray corresponding to the specified hex slice.
    """
    strhex = raw.hex()
    return bytearray.fromhex(strhex[start:end])


def aes_encrypt(message: str, key: bytes, iv: bytes) -> str:
    """
    Encrypts a string using AES-128 in CBC mode with zero-padding.

    Args:
        message: The string message to encrypt.
        key: The 16-byte encryption key.
        iv: The 16-byte initialization vector (IV).

    Returns:
        A base64-encoded string of the encrypted data.
    """
    raw = pad_zero(message.encode())
    cipher = AES.new(key, AES.MODE_CBC, iv)
    enc = cipher.encrypt(raw)
    return base64.b64encode(enc).decode("utf-8")


def aes_decrypt(enc: str, key: bytes, iv: bytes) -> bytes:
    """
    Decrypts a base64-encoded string using AES-128 in CBC mode.

    Args:
        enc: The base64-encoded encrypted string.
        key: The 16-byte decryption key.
        iv: The 16-byte initialization vector (IV).

    Returns:
        The decrypted data as bytes, after removing zero-padding.
    """
    decoded = base64.b64decode(enc)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    dec = cipher.decrypt(decoded)
    return unpad_zero(dec)


def rotate_iv_from_ciphertext(enc: str) -> bytes:
    """
    Extracts the last 16 bytes from a ciphertext to be used as the next IV.

    This is a common technique in some protocols to chain IVs.

    Args:
        enc: The base64-encoded ciphertext.

    Returns:
        The last 16 bytes of the raw ciphertext.
    """
    decoded_hex = base64.b64decode(enc).hex()
    # The last 16 bytes are the last 32 characters of the hex string.
    return bytearray.fromhex(decoded_hex[-32:])


# Specifies the public API of this module.
__all__ = [
    "aes_decrypt",
    "aes_encrypt",
    "extract_bits",
    "hmac_for_key_and_data",
    "pad_zero",
    "rotate_iv_from_ciphertext",
    "unpad_zero",
]
