import tornado.ioloop
import tornado.web
import time
import json
import os
import base64
import logging

# No encryption

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write(
            {'message': "The current time is {}".format(time.time())}
        )

    def post(self):
        data = json.loads(self.request.body.decode('utf-8'))
        self.write({'original_text': data['cipher_text'], 'plaintext': data['cipher_text']})

# Symmetric encryption with key exchange via GET.  Bad practice -- don't do this!

from cryptography.fernet import Fernet
SYMMETRIC_KEY = Fernet.generate_key()
f = Fernet(SYMMETRIC_KEY)

class EncryptedHandler(tornado.web.RequestHandler):
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
        self.write({'ciphertext': cipher_text, 'plaintext': plaintext})

# Asymmetric encryption with the server's public key, which is queried in the initial GET.  This provides
# message privacy in a reasonable way.

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

PRIVATE_KEY = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
    backend=default_backend()
)
PUBLIC_KEY = PRIVATE_KEY.public_key()

class ServerPublicKeyHandler(tornado.web.RequestHandler):

    def get(self):
        # provide the public key.  This is not bad...  It is, after all, the public key
        pem = PUBLIC_KEY.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        self.write({'publicKey': pem.decode('ASCII')})

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

# Transfer a symmetric key -- kinda like the first example.  But this example uses the client's public key
# to encrypt the symmetric key, so it is safe from snooping.

class ServerPublicKeyExchangeHandler(tornado.web.RequestHandler):

    def get(self):
        encodedClientPublicKey = self.request.query_arguments['client_publicKey'][0]
        clientPublicKeyBytes = base64.b64decode(encodedClientPublicKey)
        clientPublicKey = serialization.load_der_public_key(clientPublicKeyBytes, backend=default_backend())
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
    port = 9100
    app = tornado.web.Application([
        (r"/", MainHandler),
        (r"/encrypted/", EncryptedHandler),
        (r"/serverPublicKey/", ServerPublicKeyHandler),
        (r"/serverPublicKeySymmetricKeyExchange/", ServerPublicKeyExchangeHandler)
       ], debug = True) #turn off debugging for production

    app.listen(port)
    print("Listening on port {}".format(port))
    tornado.ioloop.IOLoop.current().start()
    #Restart Kernel to stop
except OSError:
    os._exit(00)
    #Be sure to run all

if __name__ == "__main__":
    main()

