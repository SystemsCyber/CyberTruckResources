import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

import base64

def main():
    r = requests.get("http://localhost:9100/serverPublicKey/")
    jsonReply = r.json()
    serverPublicKeyPEM = jsonReply['publicKey'].encode('ASCII')
    serverPublicKey = serialization.load_pem_public_key(serverPublicKeyPEM, backend=default_backend())

    plain_text = "I have a dream that my four little children will one day live in a nation where they will not be judged by the color of their skin but by the content of their character."
    encodedPlainText = plain_text.encode('utf-8')
    encrypted = serverPublicKey.encrypt(encodedPlainText,
                                        padding.OAEP(
                                            mgf=padding.MGF1(algorithm=hashes.SHA256()),
                                            algorithm=hashes.SHA256(),
                                            label=None)
                                        )

    encryptedB64 = base64.b64encode(encrypted)
    encryptedB64ASCII = encryptedB64.decode('ASCII')

    r = requests.post("http://localhost:9100/serverPublicKey/",
                      json={'cipher_text': encryptedB64ASCII})
    reply = r.json()
    print(reply['plaintext'])

    pass

if __name__ == "__main__":
    main()