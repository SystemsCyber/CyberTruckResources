import tornado.ioloop
import tornado.web
import time
import json
import os
import base64
import logging
import requests

from cryptography.fernet import Fernet

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric import padding

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


SYMMETRIC_KEY = Fernet.generate_key()
SERVER_SYMMETRIC_KEY = None
PRIVATE_KEY = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
    backend=default_backend()
)
PUBLIC_KEY = PRIVATE_KEY.public_key()

class EncryptedHandler(tornado.web.RequestHandler):

    def sendFakeMessageToServer(self, msg):
        f = Fernet(SERVER_SYMMETRIC_KEY)
        plain_text = msg
        cipher_text = f.encrypt(plain_text.encode('utf-8'))
        r = requests.post(f"http://localhost:9100/encrypted/", json={'cipher_text': cipher_text.decode('utf-8'), })
        reply = r.json()
        logging.debug(f"Successfully sent fake message to server!!!  Reply: {reply}")

    def get(self):
        #Write the key data out
        # Don't ever do this. It is bad. You'll expose the key!
        self.write({'key': SYMMETRIC_KEY.decode('utf-8')})

    def post(self):
        data = json.loads(self.request.body.decode('utf-8'))
        logging.debug(f'Got JSON data: {data}')
        cipher_text = data['cipher_text']
        f = Fernet(SYMMETRIC_KEY)
        plaintext = f.decrypt(cipher_text.encode('utf-8')).decode('utf-8')
        logging.debug(f"Got the super secret message!!!  It is '{plaintext}'")
        fake_message = 'Jerry is a stinker!'
        self.sendFakeMessageToServer(fake_message)
        self.write({'ciphertext': cipher_text, 'plaintext': fake_message})

class ServerPublicKeyExchangeHandler(tornado.web.RequestHandler):

    def getSymmetricKeyFromServer(self):
        global SERVER_SYMMETRIC_KEY
        pitmPublicKey = base64.b64encode(PUBLIC_KEY.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo))
        r = requests.get(f"http://localhost:9100/serverPublicKeySymmetricKeyExchange/", {'client_publicKey': pitmPublicKey})
        jsonReply = r.json()
        encodedEncryptedSymmetricKey = jsonReply['encodedEncryptedSymmetricKey']
        encryptedSymmetricKey = base64.b64decode(encodedEncryptedSymmetricKey)
        SERVER_SYMMETRIC_KEY = PRIVATE_KEY.decrypt(encryptedSymmetricKey,
                                           padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),
                                                        algorithm=hashes.SHA256(),
                                                        label=None))
        return SYMMETRIC_KEY

    def get(self):
        encodedClientPublicKey = self.request.query_arguments['client_publicKey'][0]
        clientPublicKeyBytes = base64.b64decode(encodedClientPublicKey)
        clientPublicKey = serialization.load_der_public_key(clientPublicKeyBytes, backend=default_backend())
        serverSymmKey = self.getSymmetricKeyFromServer()
        # provide the symmetric key, but encrypt it with the client public key to keep it secret
        logging.debug(f"Symmetric key: {SYMMETRIC_KEY}")
        encryptedSymmetricKey = clientPublicKey.encrypt(SYMMETRIC_KEY,
                                                        padding.OAEP(
                                                            mgf=padding.MGF1(algorithm=hashes.SHA256()),
                                                            algorithm=hashes.SHA256(),
                                                            label=None)
                                                        )
        encodedEncryptedSymmetricKey = base64.b64encode(encryptedSymmetricKey).decode('utf-8')
        self.write({'encodedEncryptedSymmetricKey': encodedEncryptedSymmetricKey})

    def post(self):
        data = json.loads(self.request.body.decode('utf-8'))
        cyphertext = data['cipher_text']
        logging.debug(f"Cyphertext: {cyphertext}")
        cypherbytes = base64.b64decode(cyphertext)
        logging.debug(f"Cypherbytes: {cypherbytes}")

        try:
            plaintext = PRIVATE_KEY.decrypt(
                cypherbytes,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
        except ValueError as e:
            logging.warning(f"Value Error: {e}")
            plaintext = None
        self.write({'original_text': data['cipher_text'], 'plaintext': plaintext.decode('utf-8')})

def main():
    try:
        logging.basicConfig(level=logging.DEBUG)
        port = 9101
        app = tornado.web.Application([
            (r"/encrypted/", EncryptedHandler),
            (r"/serverPublicKeySymmetricKeyExchange/", ServerPublicKeyExchangeHandler)
           ], debug=True) #turn off debugging for production

        app.listen(port)
        print("Listening on port {}".format(port))
        tornado.ioloop.IOLoop.current().start()
        #Restart Kernel to stop
    except OSError:
        os._exit(00)
        #Be sure to run all

if __name__ == "__main__":
    main()