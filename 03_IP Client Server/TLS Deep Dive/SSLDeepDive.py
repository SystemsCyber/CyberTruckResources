
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidSignature
from datetime import datetime, timedelta

def selfSignedCertificateExample():
    privateKey = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )

    publicKey = privateKey.public_key()

    issuer = x509.Name([
        x509.NameAttribute(x509.NameOID.COUNTRY_NAME,           u"US"),
        x509.NameAttribute(x509.NameOID.STATE_OR_PROVINCE_NAME, u"Colorado"),
        x509.NameAttribute(x509.NameOID.LOCALITY_NAME,          u"Fort Collins"),
        x509.NameAttribute(x509.NameOID.ORGANIZATION_NAME,      u"Colorado State University"),
        x509.NameAttribute(x509.NameOID.COMMON_NAME,            u"fakesite.edu")
    ])

    subject = issuer
    rawCert = (
        x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(publicKey)
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.utcnow())
            .not_valid_after(datetime.utcnow() + timedelta(days=10))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(u"localhost")]), critical=False)
            )

    signedCert = rawCert.sign(privateKey, hashes.SHA256(), backend=default_backend())

    try:
        publicKey.verify(
            signedCert.signature,
            signedCert.tbs_certificate_bytes,
            padding.PKCS1v15(),
            signedCert.signature_hash_algorithm
        )
    except InvalidSignature as e:
        print("Invalid signature")
        return False
    print("Valid signature")
    return True

from OpenSSL import SSL
import certifi
import socket
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import padding


HOSTNAME = 'api.github.com'
DEST_IPADDR = '140.82.112.3'
PORT = 443

def verifyTLSCert():
    context = SSL.Context(method=SSL.TLSv1_2_METHOD)
    context.load_verify_locations(cafile=certifi.where())

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        conn = SSL.Connection(context, socket=s)
        conn.settimeout(5)
        conn.connect((DEST_IPADDR, PORT))
        conn.setblocking(1)
        conn.do_handshake()
        peerCert = conn.get_peer_certificate()
        certChain = conn.get_peer_cert_chain()

    CACert = certChain[-1].to_cryptography()
    pktCert = peerCert.to_cryptography()

    #
    # Verify certificate w/ CA public key
    #

    try:
        CACert.public_key().verify(
            pktCert.signature,
            pktCert.tbs_certificate_bytes,
            padding.PKCS1v15(),
            pktCert.signature_hash_algorithm
        )
    except InvalidSignature as e:
        print("Invalid signature")
        return False

    #
    # todo: verify server name & validity interval
    #

    #
    # todo: verify hash against hash encrypted w/ server private key
    #

    print("Valid signature")
    return True

def main():
    selfSignedCertificateExample()
    verifyTLSCert()

if __name__ == "__main__":
    main()

pass
