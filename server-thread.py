import socket
import struct
import os
from threading import Thread

def recv_msg(sock):
    header = sock.recv(4)

    if len(header) < 4:
        return None

    length = struct.unpack(">I", header)[0]

    buffer = b''
    while len(buffer) < length:
        buffer += sock.recv(length - len(buffer))

    return buffer

def send_msg(sock, data):
    header = struct.pack(">I", len(data))
    sock.sendall(header + data)

def send_file(sock, path, chunk_size=4096):
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            sock.sendall(struct.pack(">I", len(chunk)) + chunk)
    sock.sendall(struct.pack(">I", 0))

def recv_file(sock, path):
    with open(path, "wb") as f:
        while True:
            length = struct.unpack(">I", sock.recv(4))[0]
            if length == 0:
                break
            buffer = b""
            while len(buffer) < length:
                buffer += sock.recv(length - len(buffer))
            f.write(buffer)

class Server:
    def __init__(self, host, port, root_dir):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((host, port))
        self.socket.listen()

        self.clients = []

        self.root_dir = os.path.expanduser(root_dir)

    def run(self):
        try:
            while True:
                client_sock, client_addr = self.socket.accept()
                print(f"Connected by {client_addr}")

                client = {'client_socket': client_sock, 'client_addr': client_addr}

                self.clients.append(client)
                Thread(target = self.handle_new_client, args=(client,)).start()                    
        except KeyboardInterrupt:
            self.socket.close()

            for client in self.clients:
                client['client_socket'].close()
    
    def handle_new_client(self, client):
        client_sock = client['client_socket']
        running = 1
        while running:
            data = recv_msg(client_sock)

            if not data:
                self.clients.remove(client)
                client_sock.close()
                running = 0
                break

            command = data.decode()

            if command.startswith('/list'):
                self.handle_list(client_sock)
            elif command.startswith('/upload'):
                filename = command.split(maxsplit=1)[1]
                self.handle_upload(client_sock, filename)
            elif command.startswith('/download'):
                filename = command.split(maxsplit=1)[1]
                self.handle_download(client_sock, filename)  
    
    def handle_list(self, sock):
        filenames = []
        
        with os.scandir(self.root_dir) as entries:
            for entry in entries:
                if entry.is_file():
                    filenames.append(entry.name)

        send_msg(sock, ("\n".join(filenames) + "\n").encode())

    def handle_upload(self, sock, filename):
        filepath = f"{self.root_dir}/{filename}"
        recv_file(sock, filepath)

    def handle_download(self, sock, filename):
        filepath = f"{self.root_dir}/{filename}"
        send_file(sock, filepath)

if __name__ == "__main__":
    server = Server("127.0.0.1", 6767, '~')
    server.run()