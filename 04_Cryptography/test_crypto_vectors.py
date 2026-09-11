"""Known-answer tests for the primitives used in SYSE 549 module 04.

Every vector here is published. Sources are cited per test:
  FIPS 197    Advanced Encryption Standard
  FIPS 180-4  Secure Hash Standard (SHA-1, SHA-2)
  FIPS 202    SHA-3 Standard
  SP 800-38D  GCM and GMAC
  RFC 4231    HMAC-SHA-2 test vectors
  RFC 5869    HKDF
  RFC 7748    X25519
  RFC 8032    Ed25519

Run with:      pytest -v test_crypto_vectors.py
Quiet:         pytest -q
One test:      pytest -k gcm
Stop on first: pytest -x
"""
import hashlib
import pytest

from cryptography.hazmat.primitives import hashes, hmac
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.asymmetric import x25519, ed25519
from cryptography.exceptions import InvalidTag


def h(s):
    """Hex string (whitespace allowed) to bytes -- how the standards print vectors."""
    return bytes.fromhex(s.replace(" ", "").replace("\n", ""))


# ---------------------------------------------------------------- simplest possible test
def test_fips197_aes128_appendix_c1():
    """FIPS 197 Appendix C.1: one AES-128 block, key and plaintext fixed by the standard."""
    encryptor = Cipher(algorithms.AES(h("000102030405060708090a0b0c0d0e0f")),
                       modes.ECB()).encryptor()
    ciphertext = encryptor.update(h("00112233445566778899aabbccddeeff")) + encryptor.finalize()
    assert ciphertext == h("69c4e0d86a7b0430d8cdb78070b4c55a")


# ---------------------------------------------------------------- parametrize: one test, many vectors
# Each tuple becomes its own test case with its own pass/fail line in the report.
AES_KAT = [
    ("AES-128", "000102030405060708090a0b0c0d0e0f",
     "69c4e0d86a7b0430d8cdb78070b4c55a"),
    ("AES-192", "000102030405060708090a0b0c0d0e0f1011121314151617",
     "dda97ca4864cdfe06eaf70a0ec0d7191"),
    ("AES-256", "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f",
     "8ea2b7ca516745bfeafc49904b496089"),
]

@pytest.mark.parametrize("name,key,expected", AES_KAT, ids=[k[0] for k in AES_KAT])
def test_fips197_all_key_sizes(name, key, expected):
    """FIPS 197 Appendix C.1-C.3: the same plaintext under all three approved key sizes."""
    encryptor = Cipher(algorithms.AES(h(key)), modes.ECB()).encryptor()
    assert (encryptor.update(h("00112233445566778899aabbccddeeff"))
            + encryptor.finalize()).hex() == expected


HASH_KAT = [
    ("sha256",   hashlib.sha256,
     "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"),
    ("sha512",   hashlib.sha512,
     "ddaf35a193617abacc417349ae20413112e6fa4e89a97ea20a9eeee64b55d39a"
     "2192992a274fc1a836ba3c23a3feebbd454d4423643ce80e2a9ac94fa54ca49f"),
    ("sha3_256", hashlib.sha3_256,
     "3a985da74fe225b2045c172d6bd390bd855f086e3e9d525b46bfe24511431532"),
]

@pytest.mark.parametrize("name,fn,expected", HASH_KAT, ids=[k[0] for k in HASH_KAT])
def test_hash_abc(name, fn, expected):
    """FIPS 180-4 and FIPS 202 worked examples for the message b"abc"."""
    assert fn(b"abc").hexdigest() == expected


# ---------------------------------------------------------------- fixture: build a thing once
@pytest.fixture
def gcm_vector():
    """SP 800-38D / McGrew-Viega Test Case 3. A fixture keeps the vector out of the test body."""
    return {
        "key": h("feffe9928665731c6d6a8f9467308308"),
        "iv":  h("cafebabefacedbaddecaf888"),
        "pt":  h("d9313225f88406e5a55909c5aff5269a86a7a9531534f7da2e4c303d8a318a72"
                 "1c3c0c95956809532fcf0e2449a6b525b16aedf5aa0de657ba637b391aafd255"),
        "ct":  h("42831ec2217774244b7221b784d0d49ce3aa212f2c02a4e035c17e2329aca12e"
                 "21d514b25466931c7d8f6a5aac84aa051ba30b396a0aac973d58e091473f5985"
                 "4d5c2af327cd64a62cf35abd2ba6fab4"),
    }


def test_gcm_encrypt_matches_published_vector(gcm_vector):
    """A test that asks for `gcm_vector` gets it -- pytest matches on the argument name."""
    v = gcm_vector
    assert AESGCM(v["key"]).encrypt(v["iv"], v["pt"], None) == v["ct"]


def test_gcm_decrypt_round_trip(gcm_vector):
    """The same fixture, freshly built, for a second independent test."""
    v = gcm_vector
    assert AESGCM(v["key"]).decrypt(v["iv"], v["ct"], None) == v["pt"]


# ---------------------------------------------------------------- negative test: it must FAIL
def test_gcm_rejects_tampering(gcm_vector):
    """The security property is that a modified ciphertext does NOT decrypt.

    pytest.raises asserts that the block raises -- if decrypt() returned plaintext here,
    the test fails, which is exactly what we want to know.
    """
    v = gcm_vector
    tampered = bytearray(v["ct"])
    tampered[0] ^= 0x01
    with pytest.raises(InvalidTag):
        AESGCM(v["key"]).decrypt(v["iv"], bytes(tampered), None)


def test_gcm_rejects_wrong_associated_data(gcm_vector):
    """Associated data is authenticated: changing it must break verification."""
    v = gcm_vector
    token = AESGCM(v["key"]).encrypt(v["iv"], b"value=1450", b"src=0x00;seq=0x0417")
    with pytest.raises(InvalidTag):
        AESGCM(v["key"]).decrypt(v["iv"], token, b"src=0x17;seq=0x0417")


# ---------------------------------------------------------------- MACs and KDFs
def test_rfc4231_hmac_sha256_case1():
    """RFC 4231 test case 1: 20 bytes of 0x0b as the key, b"Hi There" as the message."""
    m = hmac.HMAC(b"\x0b" * 20, hashes.SHA256())
    m.update(b"Hi There")
    assert m.finalize() == h("b0344c61d8db38535ca8afceaf0bf12b"
                             "881dc200c9833da726e9376c2e32cff7")


def test_rfc5869_hkdf_sha256_case1():
    """RFC 5869 Appendix A.1: 42 bytes of output key material."""
    okm = HKDF(algorithm=hashes.SHA256(), length=42,
               salt=h("000102030405060708090a0b0c"),
               info=h("f0f1f2f3f4f5f6f7f8f9")).derive(b"\x0b" * 22)
    assert okm == h("3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db0"
                    "2d56ecc4c5bf34007208d5b887185865")


# ---------------------------------------------------------------- public key vectors
def test_rfc7748_x25519_section_6_1():
    """RFC 7748 Sec. 6.1: both public keys and the shared secret are published."""
    a = x25519.X25519PrivateKey.from_private_bytes(
        h("77076d0a7318a57d3c16c17251b26645df4c2f87ebc0992ab177fba51db92c2a"))
    b = x25519.X25519PrivateKey.from_private_bytes(
        h("5dab087e624a8a4b79e17f8b83800ee66f3bb1292618b6fd1c2f8b27ff88e0eb"))
    assert a.public_key().public_bytes_raw() == h(
        "8520f0098930a754748b7ddcb43ef75a0dbf3a0d26381af4eba4a98eaa9b4e6a")
    assert a.exchange(b.public_key()) == h(
        "4a5d9d5ba4ce2de1728e3bf480350f25e07e21c947d19e3376f09b3c1e161742")
    assert a.exchange(b.public_key()) == b.exchange(a.public_key())


def test_rfc8032_ed25519_test1_is_deterministic():
    """RFC 8032 Sec. 7.1 TEST 1. Ed25519 is deterministic, so the exact bytes are testable."""
    sk = ed25519.Ed25519PrivateKey.from_private_bytes(
        h("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"))
    assert sk.public_key().public_bytes_raw() == h(
        "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
    assert sk.sign(b"") == h(
        "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155"
        "5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b")


# ---------------------------------------------------------------- xfail: a documented break
MD5_COLLISION_A = h(
    "d131dd02c5e6eec4693d9a0698aff95c2fcab58712467eab4004583eb8fb7f89"
    "55ad340609f4b30283e488832571415a085125e8f7cdc99fd91dbdf280373c5b"
    "d8823e3156348f5bae6dacd436c919c6dd53e2b487da03fd02396306d248cda0"
    "e99f33420f577ee8ce54b67080a80d1ec69821bcb6a8839396f9652b6ff72a70")
MD5_COLLISION_B = h(
    "d131dd02c5e6eec4693d9a0698aff95c2fcab50712467eab4004583eb8fb7f89"
    "55ad340609f4b30283e4888325f1415a085125e8f7cdc99fd91dbd7280373c5b"
    "d8823e3156348f5bae6dacd436c919c6dd53e23487da03fd02396306d248cda0"
    "e99f33420f577ee8ce54b67080280d1ec69821bcb6a8839396f965ab6ff72a70")


@pytest.mark.xfail(strict=True,
                   reason="MD5 collision resistance is broken (Wang et al., 2004)")
def test_md5_is_collision_resistant():
    """Asserts the property MD5 is SUPPOSED to have. It does not have it.

    strict=True means the suite FAILS if this ever unexpectedly passes -- which would
    mean the vectors were edited. This is how you keep a known break documented and
    under test instead of deleting the evidence.
    """
    assert hashlib.md5(MD5_COLLISION_A).digest() != hashlib.md5(MD5_COLLISION_B).digest()


def test_sha256_separates_the_md5_collision_pair():
    """The same two inputs, under a hash that is not broken. This one must pass."""
    assert MD5_COLLISION_A != MD5_COLLISION_B
    assert hashlib.sha256(MD5_COLLISION_A).digest() != hashlib.sha256(MD5_COLLISION_B).digest()
