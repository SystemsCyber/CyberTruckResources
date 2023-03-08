import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from cryptography.fernet import Fernet

import base64

PRIVATE_KEY = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
    backend=default_backend()
)
PUBLIC_KEY = PRIVATE_KEY.public_key()
PORT = 9100  # set this here so we can reuse app for PITM

def main():
encodedClientPublicKey = base64.b64encode(PUBLIC_KEY.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo))
r = requests.get(f"http://localhost:{PORT}/serverPublicKeySymmetricKeyExchange/", {'client_publicKey': encodedClientPublicKey})
jsonReply = r.json()
encodedEncryptedSymmetricKey = jsonReply['encodedEncryptedSymmetricKey']
encryptedSymmetricKey = base64.b64decode(encodedEncryptedSymmetricKey)
symmetricKey = PRIVATE_KEY.decrypt(encryptedSymmetricKey, padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),
                                                                      algorithm=hashes.SHA256(),
                                                                      label=None))
f = Fernet(symmetricKey)
plain_text = "I have a dream that my four little children will one day live in a nation where they will not be judged by the color of their skin but by the content of their character."
cipher_text = f.encrypt(plain_text.encode('utf-8'))
r = requests.post(f"http://localhost:{PORT}/encrypted/", json={'cipher_text': cipher_text.decode('utf-8'), })
reply = r.json()
print(reply['plaintext'])

    pass

if __name__ == "__main__":
    main()