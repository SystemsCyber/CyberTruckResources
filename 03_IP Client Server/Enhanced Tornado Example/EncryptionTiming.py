import logging
from cryptography.fernet import Fernet
from Timer import Timer
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

NUM_SYMMETRIC_ITERATIONS = 1000
NUM_ASYMMETRIC_ITERATIONS = 100

plain_text = "I have a dream that my four little children will one day live in a nation where they will not be judged by the color of their skin but by the content of their character."
plain_text_bytes = plain_text.encode('utf-8')

key = Fernet.generate_key()
f = Fernet(key)

privateKey = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
    backend=default_backend()
)
publicKey = privateKey.public_key()

def symmetricKeyTiming():
    with Timer("Symmetric Encryptions") as t0:
        t0.setCount(NUM_SYMMETRIC_ITERATIONS)
        for _ in range(NUM_SYMMETRIC_ITERATIONS):
            cipher_text = f.encrypt(plain_text_bytes)
            cleartext = f.decrypt(cipher_text)
            if cleartext != plain_text_bytes:
                logging.warning(f"Cleartext '{cleartext}' differs from plain_text '{plain_text_bytes}")
                break

def asymmetricKeyEncryptionTiming():

    # set up keys & padding

    padSpec = padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None)

    with Timer("Asymmetric Encryptions") as t0:
        t0.setCount(NUM_ASYMMETRIC_ITERATIONS)
        for _ in range(NUM_ASYMMETRIC_ITERATIONS):
            ciphertext = publicKey.encrypt(plain_text_bytes, padSpec)
            cleartext = privateKey.decrypt(ciphertext, padSpec)
            if cleartext != plain_text_bytes:
                logging.warning(f"Cleartext '{cleartext}' differs from plain_text '{plain_text_bytes}")
                break

def asymmetricKeySigningTiming():

    # set up keys & padding

    padSpec = padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH)

    with Timer("Asymmetric Signing") as t0:
        t0.setCount(NUM_ASYMMETRIC_ITERATIONS)
        for _ in range(NUM_ASYMMETRIC_ITERATIONS):
            sig = privateKey.sign(plain_text_bytes, padSpec, hashes.SHA256())
            publicKey.verify(sig, plain_text_bytes, padSpec, hashes.SHA256())


def main():
    logging.basicConfig(level=logging.INFO)
    symmetricKeyTiming()
    asymmetricKeyEncryptionTiming()
    asymmetricKeySigningTiming()
    pass

if __name__ == "__main__":
    main()