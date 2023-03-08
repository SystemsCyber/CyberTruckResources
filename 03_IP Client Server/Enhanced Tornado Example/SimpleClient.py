import requests

def main():
    plain_text = "I have a dream that my four little children will one day live in a nation where they will not be judged by the color of their skin but by the content of their character."


    r = requests.post("http://localhost:9100/",
                      json={'cipher_text': plain_text})
    reply = r.json()
    print(reply['plaintext'])

    pass

if __name__ == "__main__":
    main()