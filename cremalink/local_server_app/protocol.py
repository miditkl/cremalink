"""
This module implements the low-level cryptographic protocol for communicating
with the De'Longhi device over the local network. It handles session key
derivation, payload encryption/decryption, and message signing.
"""
import base64
import json
from typing import Tuple

from cremalink.crypto import (
    aes_decrypt, aes_encrypt, extract_bits, hmac_for_key_and_data,
    rotate_iv_from_ciphertext
)


def pad_seq(seq: int) -> str:
    """Pads the sequence number as a string (currently a no-op)."""
    return str(seq)


def derive_keys(
    lan_key: str, random_1: str, random_2: str, time_1: str, time_2: str
) -> Tuple[bytes, bytes, bytes, bytes, bytes]:
    """
    Derives all necessary session keys from the initial key exchange parameters.

    The key derivation process is a specific, non-standard protocol that uses
    a series of HMAC-SHA256 operations on concatenated inputs (random values,
    timestamps, and a final byte that varies for each key type). This creates
    unique keys for signing, client-side encryption, and server-side encryption.

    Args:
        lan_key: The main secret key for the device on the LAN.
        random_1: The random value from the device (client).
        random_2: The random value from this server (host).
        time_1: The timestamp from the device (client).
        time_2: The timestamp from this server (host).

    Returns:
        A tuple containing the five derived keys:
        (app_sign_key, app_crypto_key, app_iv_seed, dev_crypto_key, dev_iv_seed)
    """
    rnd_1s = random_1.encode("utf-8")
    rnd_2s = random_2.encode("utf-8")
    time_1s = str(time_1).encode("utf-8")
    time_2s = str(time_2).encode("utf-8")
    lan_key_bytes = lan_key.encode("utf-8")

    # --- Application (Client-Side) Keys ---

    # 1. Application Signing Key
    lastbyte = b"\x30"
    concat = rnd_1s + rnd_2s + time_1s + time_2s + lastbyte
    app_sign_key = hmac_for_key_and_data(
        lan_key_bytes, hmac_for_key_and_data(lan_key_bytes, concat) + concat
    )

    # 2. Application Encryption Key
    lastbyte = b"\x31"
    concat = rnd_1s + rnd_2s + time_1s + time_2s + lastbyte
    app_crypto_key = hmac_for_key_and_data(
        lan_key_bytes, hmac_for_key_and_data(lan_key_bytes, concat) + concat
    )

    # 3. Application IV Seed (for AES-CBC)
    lastbyte = b"\x32"
    concat = rnd_1s + rnd_2s + time_1s + time_2s + lastbyte
    app_iv_seed = extract_bits(
        hmac_for_key_and_data(lan_key_bytes, hmac_for_key_and_data(lan_key_bytes, concat) + concat),
        0,
        16 * 2,  # Extract 16 bytes (32 hex chars)
    )

    # --- Device (Server-Side) Keys ---
    # Note the reversed order of randoms and timestamps.

    # 4. Device Encryption Key
    lastbyte = b"\x31"
    concat = rnd_2s + rnd_1s + time_2s + time_1s + lastbyte
    dev_crypto_key = hmac_for_key_and_data(
        lan_key_bytes, hmac_for_key_and_data(lan_key_bytes, concat) + concat
    )

    # 5. Device IV Seed (for AES-CBC)
    lastbyte = b"\x32"
    concat = rnd_2s + rnd_1s + time_2s + time_1s + lastbyte
    dev_iv_seed = extract_bits(
        hmac_for_key_and_data(lan_key_bytes, hmac_for_key_and_data(lan_key_bytes, concat) + concat),
        0,
        16 * 2,  # Extract 16 bytes (32 hex chars)
    )

    return app_sign_key, app_crypto_key, app_iv_seed, dev_crypto_key, dev_iv_seed


def encrypt_payload(payload: str, crypto_key: bytes, iv_seed: bytes) -> Tuple[str, bytes]:
    """
    Encrypts a payload string using AES-CBC and returns the new IV.

    The IV for the next encryption is derived from the ciphertext of the current one.

    Returns:
        A tuple containing the base64-encoded ciphertext and the next IV.
    """
    enc = aes_encrypt(payload, crypto_key, iv_seed)
    new_iv = rotate_iv_from_ciphertext(enc)
    return enc, new_iv


def decrypt_payload(enc: str, crypto_key: bytes, iv_seed: bytes) -> Tuple[bytes, bytes]:
    """
    Decrypts a base64-encoded ciphertext and returns the new IV.

    The IV for the next decryption is derived from the ciphertext of the current one.

    Returns:
        A tuple containing the decrypted plaintext (bytes) and the next IV.
    """
    decrypted = aes_decrypt(enc, crypto_key, iv_seed)
    new_iv = rotate_iv_from_ciphertext(enc)
    return decrypted, new_iv


def sign_payload(payload: str, sign_key: bytes) -> str:
    """
    Signs a payload string using HMAC-SHA256 and returns the base64-encoded signature.
    """
    return base64.b64encode(hmac_for_key_and_data(sign_key, payload.encode("utf-8"))).decode("utf-8")


def build_empty_payload(seq: int) -> str:
    """
    Creates a JSON string for an empty command payload, used as a heartbeat.
    """
    return json.dumps({"seq_no": pad_seq(seq), "data": {}}, separators=(",", ":"))
