# Module 04 — Cryptography

**SYSE 549: Secure Vehicle and Industrial Networking**

Five notebooks that build symmetric cryptography, public-key cryptography, key agreement
and digital signatures from primitives, then verify every one of them against the published
test vector that defines it.

**Each notebook is self-contained.** None of them refers to any of the others, so they can
be assigned individually, reordered, or dropped into another course without editing. The
only sequencing implied is what the titles suggest.

Examples are drawn primarily from **Transport Layer Security (TLS) 1.3**, **data at rest**
(disk, database and archive encryption) and **industrial control systems**, with embedded
and vehicle networking as one setting among several. Where a constrained bus is discussed,
the 8-byte payload limit of a classic Controller Area Network (CAN) frame is stated
explicitly, along with what it forces: CAN FD, a segmenting transport protocol
(ISO 15765-2, SAE J1939 TP.CM/TP.DT, NMEA 2000 fast packets), or a deliberately truncated
MAC.

Every notebook opens with an **acronym table**, and each acronym is expanded again on its
first few appearances in the text.

## Files

| File | Role |
|---|---|
| `04a Cryptographic Primitives - Symmetric.ipynb` | Challenge-response, AES modes, hash functions and the MD5 break, Fernet dissected, HMAC, AES-GCM |
| `04b Crypto Primitives - Asymmetric.ipynb` | RSA, OAEP, the size limit, envelope encryption (DEK/KEK), HPKE |
| `04c Crypto Primitives - ECDH.ipynb` | X25519 key agreement, HKDF, forward secrecy, ML-KEM |
| `04d Crypto Primitives - ECDSA.ipynb` | RSA-PSS, ECDSA on P-256, nonce reuse, Ed25519, ML-DSA |
| `04f Standards and Test Vectors.ipynb` | 53 published known-answer tests, plus an introduction to `pytest` |
| `test_crypto_vectors.py` | The test suite 04f writes and runs. Runnable on its own with `pytest`. |
| `test_vectors_from_file.py` | Same idea, parametrized from an external vector file |
| `aes_ecb_vectors.json` | Example vector file (FIPS 197 Appendix C) |
| `_originals_backup/` | The four notebooks exactly as they were before this revision |

Notebooks 04a–04d are the lecture material and 04f is a reference and a lab, but none of them depends on another. Assign them in any order.

## Running them

```
pip install --upgrade cryptography pytest
```

Verified against `cryptography` 50.0.0 on Python 3.10. The post-quantum cells (ML-KEM,
ML-DSA, HPKE) are wrapped in `try/except` and skip cleanly on older installs; nothing else
depends on them.

**One cell in 04a raises on purpose** — the HMAC verification-failure demonstration, which
is labelled as such. Every other cell in every notebook runs clean under "Run All."

## Prompt engineering: the "Try It Yourself" blocks

Each of 04a–04d contains one **Try It Yourself** exercise. They are not fill-in-the-blank
syntax drills; they ask the student to *specify* a piece of cryptographic code precisely
enough that a language model produces a correct implementation, and to verify it against a
test written before the code existed.

Each block gives four things:

1. A **weak prompt** — the kind most people type.
2. The list of what a good prompt must pin down (library and version, exact primitive and
   parameters, the interface, what must *not* happen, and how it will be verified).
3. A **starting prompt** to edit and hand to an assistant.
4. A fixed **acceptance test**, written in advance, that the pasted code must pass.

The rule is stated in the notebooks: **if the acceptance test fails, fix the prompt, not
the code.** Patching the output teaches nothing that transfers; rewriting the specification
until a cold model gets it right on the first try is the skill — and it is the same skill
as writing a requirement for a supplier.

| Notebook | Target | Checks |
|---|---|---|
| 04a | An AES-256-GCM `seal`/`unseal` pair | 8 |
| 04b | An envelope-encryption `wrap`/`unwrap` pair | 10 |
| 04c | A two-directional ECDH handshake with HKDF | 8 |
| 04d | A signed firmware manifest and its verifier | 8 |

The acceptance tests check **behavior**, not source strings, so aliased imports and
different-but-correct styles pass. Each has been validated against a reference solution.
An untouched notebook prints "Paste the generated code above" rather than failing, so
"Run All" still works.

The framing — what a good prompt names, and why you fix the prompt rather than the code —
is repeated inside each block, so no notebook depends on another. In 04a the block is
positioned so students specify the function *before* they see the worked answer in the
next cell.

## Testing: `pytest` in 04f

Section 12 of 04f moves from "proved once in a notebook" to "checked on every commit." It
covers:

* why a notebook is a demonstration and not a test suite;
* the anatomy of a pytest test — discovery rules, plain `assert`, assertion introspection;
* `@pytest.mark.parametrize` to run one test body over a table of vectors, with each vector
  reported under its own id;
* `@pytest.fixture` to build a shared vector or key once;
* `pytest.raises` for the negative tests that matter here — a tampered ciphertext and wrong
  associated data must *fail*;
* `@pytest.mark.xfail(strict=True)` to encode a known break: the MD5 collision-resistance
  test is expected to fail, and the suite fails if it ever unexpectedly passes;
* what a failure actually looks like (written to a temp directory so it never pollutes this
  folder), and how to parametrize from an external vector file — the bridge to CAVP `.rsp`
  files and Wycheproof JSON.

From this folder:

```
pytest              # 19 passed, 1 xfailed
pytest -v           # one line per test, with parametrize ids
pytest -k gcm       # only the GCM tests
pytest --collect-only
```

The exit code is the point: 0 when everything passed, non-zero otherwise. That is the whole
contract a CI job needs, and it turns "we validated the crypto" from a claim made once into
a property checked continuously.

## Standards traceability

Every primitive is anchored to a document, and 04f runs the published known-answer test for
it. Every citation in every notebook links to the document.

| Primitive | Standard | Vector in 04f |
|---|---|---|
| AES block cipher | [FIPS 197](https://csrc.nist.gov/pubs/fips/197/final) | App. C.1/C.2/C.3 |
| ECB, CBC, CTR | [SP 800-38A](https://csrc.nist.gov/pubs/sp/800/38/a/final) | App. F.1.1, F.2.1, F.5.1 |
| CMAC (AUTOSAR SecOC) | [SP 800-38B](https://csrc.nist.gov/pubs/sp/800/38/b/final) | App. D.1 |
| AES-CCM | [SP 800-38C](https://csrc.nist.gov/pubs/sp/800/38/c/final) | — |
| AES-GCM | [SP 800-38D](https://csrc.nist.gov/pubs/sp/800/38/d/final) | Test Cases 2, 3, 4 |
| AES-GCM-SIV | [RFC 8452](https://www.rfc-editor.org/rfc/rfc8452) | Sec. 8 |
| ChaCha20-Poly1305 | [RFC 8439](https://www.rfc-editor.org/rfc/rfc8439) | Sec. 2.8.2 |
| SHA-1 / SHA-2 | [FIPS 180-4](https://csrc.nist.gov/pubs/fips/180-4/upd1/final) | `"abc"` examples |
| SHA-3 / SHAKE | [FIPS 202](https://csrc.nist.gov/pubs/fips/202/final) | `"abc"` examples |
| HMAC | [FIPS 198-1](https://csrc.nist.gov/pubs/fips/198-1/final) / [RFC 4231](https://www.rfc-editor.org/rfc/rfc4231) | TC1, TC2 |
| PBKDF2 | [SP 800-132](https://csrc.nist.gov/pubs/sp/800/132/final) / [RFC 6070](https://www.rfc-editor.org/rfc/rfc6070) | TC1, TC2 |
| HKDF | [SP 800-56C Rev. 2](https://csrc.nist.gov/pubs/sp/800/56/c/r2/final) / [RFC 5869](https://www.rfc-editor.org/rfc/rfc5869) | TC1 |
| Key derivation from a master key | [SP 800-108 Rev. 1](https://csrc.nist.gov/pubs/sp/800/108/r1/upd1/final) | — |
| ECDH / X25519 | [SP 800-56A Rev. 3](https://csrc.nist.gov/pubs/sp/800/56/a/r3/final) / [RFC 7748](https://www.rfc-editor.org/rfc/rfc7748) | Sec. 6.1 |
| RSA key establishment | [SP 800-56B Rev. 2](https://csrc.nist.gov/pubs/sp/800/56/b/r2/final) | — |
| RSA-OAEP, RSA-PSS | [RFC 8017](https://www.rfc-editor.org/rfc/rfc8017) | — (randomized) |
| Signatures (RSA, ECDSA, EdDSA) | [FIPS 186-5](https://csrc.nist.gov/pubs/fips/186-5/final) | — |
| Deterministic ECDSA | [RFC 6979](https://www.rfc-editor.org/rfc/rfc6979) | App. A.2.5 (verify) |
| Ed25519 | [RFC 8032](https://www.rfc-editor.org/rfc/rfc8032) | Sec. 7.1 TEST 1, TEST 2 |
| HPKE | [RFC 9180](https://www.rfc-editor.org/rfc/rfc9180) | — |
| Key sizes and lifetimes | [SP 800-57 Pt. 1 Rev. 5](https://csrc.nist.gov/pubs/sp/800/57/pt1/r5/final) | — |
| Random bit generation | [SP 800-90A Rev. 1](https://csrc.nist.gov/pubs/sp/800/90/a/r1/final) / [SP 800-90B](https://csrc.nist.gov/pubs/sp/800/90/b/final) | (design, not a KAT) |
| What is still approved | [SP 800-131A Rev. 2](https://csrc.nist.gov/pubs/sp/800/131/a/r2/final) | MD5 / SHA-1 status |
| MD5 (retired) | [RFC 1321](https://www.rfc-editor.org/rfc/rfc1321) | Wang collision pair |
| ML-KEM | [FIPS 203](https://csrc.nist.gov/pubs/fips/203/final) | parameter sizes + round trip |
| ML-DSA | [FIPS 204](https://csrc.nist.gov/pubs/fips/204/final) | parameter sizes + round trip |
| SLH-DSA | [FIPS 205](https://csrc.nist.gov/pubs/fips/205/final) | — |
| Module validation | [FIPS 140-3](https://csrc.nist.gov/pubs/fips/140-3/final) | — |
| PQC migration timeline | [NIST IR 8547](https://csrc.nist.gov/pubs/ir/8547/ipd) (**initial public draft**) | — |

NIST IR 8547 is still an initial public draft (November 2024). The notebooks describe its
2030 / 2035 dates as *proposed*, not as current policy.

## On Fernet

Fernet is kept as the teaching recipe, and 04a still dissects it field by field — it is the
clearest way to show what a recipe must contain. It is not broken: encrypt-then-MAC, random
IV per message, verify-before-decrypt, and no parameters for the user to set wrong.

What it cannot do, and where 04a hands off to AES-GCM:

* AES-128 only, no choice of key size
* two primitives and two passes over the data
* **no associated data** — you cannot authenticate a CAN ID, PGN or counter without encrypting it
* base64 output, 57 bytes of overhead minimum
* a mandatory clock-based timestamp, which many ECUs cannot provide
* not a NIST/FIPS construction, so it cannot appear in a FIPS 140-3 module

The end of 04a introduces **AES-256-GCM** ([SP 800-38D](https://csrc.nist.gov/pubs/sp/800/38/d/final))
as the default for new work, with the NIST test vectors, the associated-data pattern applied
to a J1939 header, the nonce rule, and a small `seal()`/`unseal()` pair students can reuse.
AES-GCM-SIV, ChaCha20-Poly1305, AES-CCM and AES-CMAC are covered in a one-screen comparison
table.

## Notes for maintaining this folder

* Re-running 04a regenerates `encrypted_logo_CBC.bmp` with a fresh random IV, so that file
  changes on every run by design. `encrypted_logo_ECB.bmp` is deterministic and does not.
* Running 04f writes `test_crypto_vectors.py`, `test_vectors_from_file.py` and
  `aes_ecb_vectors.json` into this folder. They are meant to be committed.
* `.gitignore` here covers `.pytest_cache/`, `__pycache__/` and `.ipynb_checkpoints/`.
