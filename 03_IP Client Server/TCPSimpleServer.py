import socket

HOST = '127.0.0.1'  # Standard loopback interface address (localhost)
PORT = 12354        # Port to listen on (non-privileged ports are > 1023)

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind((HOST, PORT))
s.listen()

conn, addr = s.accept()

while True:
    data = conn.recv(1024)  # block until data is available
    if not data:
        print("end of data, stopping")
        break
    print(f"received data: {data}")
    res = conn.sendall(data)
    print(f"echo done, result: {res}")
