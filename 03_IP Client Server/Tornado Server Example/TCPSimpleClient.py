import socket
import time
import os

HOST = '127.0.0.1'  # The server's hostname or IP address
PORT = 12354        # The port used by the server

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    print(s)
    for i in range(10):
        s.sendall(f'Hello, world ({os.getpid()})'.encode('UTF-8'))
        data = s.recv(1024)
        print(i, data)
        time.sleep(2)

