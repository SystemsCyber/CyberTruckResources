import socket
from threading import Thread

HOST = '127.0.0.1'  # Standard loopback interface address (localhost)
PORT = 12354        # Port to listen on (non-privileged ports are > 1023)

class EchoThread(Thread):
    def __init__(self, conn):
        super().__init__()
        self.conn = conn

    def run(self):
        print()
        print(f"Echoing {self.conn}")
        numLines = 0
        while True:
            data = self.conn.recv(1024)
            if not data:
                print("end of data, stopping")
                return
            self.conn.sendall(data)
            numLines += 1
            print(f"received data from {self.conn}")
            print(f"  data: {data}, count: {numLines}")

def main(host, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((host, port))
    s.listen()

    while True:
        print("Main thread waiting for connections")
        srvConn, addr = s.accept()
        eThread = EchoThread(srvConn)
        print(f"connection from {addr}, spawning echo thread {eThread.name}")
        eThread.start()

main(HOST, PORT)