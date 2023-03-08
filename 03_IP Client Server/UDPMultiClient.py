import socket
import os
import time

HOST = '127.0.0.1'  # The server's hostname or IP address
PORT = 12354        # The port used by the server

with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
    for i in range(10):
        s.sendto(f'Hello, world ({os.getpid()})'.encode('UTF-8'), (HOST, PORT))
        data = s.recv(1024)
        print(i, data)
        time.sleep(2)
