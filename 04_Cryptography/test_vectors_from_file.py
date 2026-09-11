"""Parametrizing over an external vector file -- the pattern used for CAVP and Wycheproof.

The loader below reads a small JSON file. Point it at a real CAVP .rsp or a Wycheproof
test group and only the parsing changes; the test body does not.
"""
import json
import pathlib

import pytest
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

VECTOR_FILE = pathlib.Path(__file__).with_name("aes_ecb_vectors.json")


def load_vectors():
    """Read the vector file at collection time so each case becomes its own test."""
    if not VECTOR_FILE.exists():
        return []
    return json.loads(VECTOR_FILE.read_text())["tests"]


VECTORS = load_vectors()


@pytest.mark.skipif(not VECTORS, reason="aes_ecb_vectors.json not found")
@pytest.mark.parametrize("case", VECTORS, ids=lambda c: c["id"])
def test_aes_ecb_vector(case):
    """One test per entry in the file. Add a row to the JSON, get a new test."""
    encryptor = Cipher(algorithms.AES(bytes.fromhex(case["key"])), modes.ECB()).encryptor()
    got = encryptor.update(bytes.fromhex(case["plaintext"])) + encryptor.finalize()
    assert got.hex() == case["ciphertext"]
