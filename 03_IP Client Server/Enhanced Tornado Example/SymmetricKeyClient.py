import requests
from cryptography.fernet import Fernet

def main():
    # Get the key (Don't actually do this)
    r = requests.get("http://localhost:9100/encrypted/")
    key = r.json()['key']
    f = Fernet(key)
    plain_text = "I have a dream that my four little children will one day live in a nation where they will not be judged by the color of their skin but by the content of their character."
    cipher_text = f.encrypt(plain_text.encode('utf-8'))
    r = requests.post("http://localhost:9100/encrypted/", json={'cipher_text': cipher_text.decode('utf-8'), })
    reply = r.json()
    print(reply['plaintext'])
    pass

if __name__ == "__main__":
    main()