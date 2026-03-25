import socket
import struct
import os
from threading import Thread

T_FREADY = 0x10
T_FCHUNK = 0x11
T_FEND = 0x12
T_FNOTFOUND = 0x19
T_MSG = 0x21

def recv_msg(sock):
    header = sock.recv(4)

    if len(header) < 4:
        return None

    length = struct.unpack(">I", header)[0]

    buffer = b''
    while len(buffer) < length:
        buffer += sock.recv(length - len(buffer))

    return buffer

def send_msg(sock, tag, data):
    header = struct.pack(">BI", tag, len(data))
    sock.sendall(header + data)

def send_file(sock, path, chunk_size=4096):
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            sock.sendall(struct.pack(">BI", T_FCHUNK, len(chunk)) + chunk)
    sock.sendall(struct.pack(">BI", T_FEND, 0))

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
                self.clients.append(client_sock)
                print(f"Connected by {client_addr}")
                self.broadcast_msg(f"Client {client_addr} has connected.", exclude_sock=client_sock)

                Thread(target=self.handle_new_client, args=(client_sock, client_addr)).start()                    
        except KeyboardInterrupt:
            self.socket.close()
            for client in self.clients:
                client.close()
    
    def handle_new_client(self, client_sock, client_addr):
        running = 1
        while running:
            header = client_sock.recv(1)

            if not header: 
                self.clients.remove(client_sock)
                client_sock.close()
                running = 0
                self.broadcast_msg(f"Client {client_addr} has disconnected", exclude_sock=client_sock)
                break

            command = recv_msg(client_sock).decode()

            if command.startswith('/list'):
                self.handle_list(client_sock)
            elif command.startswith('/upload'):
                filename = command.split(maxsplit=1)[1]
                if self.handle_upload(client_sock, filename):
                    self.broadcast_msg(f"Client {client_addr} has uploaded {filename}", exclude_sock=client_sock)
            elif command.startswith('/download'):
                filename = command.split(maxsplit=1)[1]
                if self.handle_download(client_sock, filename):
                    self.broadcast_msg(f"Client {client_addr} has successfully downloaded {filename}", exclude_sock=client_sock)  
    
    def handle_list(self, sock):
        filenames = []
        
        with os.scandir(self.root_dir) as entries:
            for entry in entries:
                if entry.is_file():
                    filenames.append(entry.name)

        send_msg(sock, T_MSG, ("\n".join(filenames) + "\n").encode())

    def handle_upload(self, sock, filename):
        filepath = os.path.join(self.root_dir, filename)
        file = open(filepath, "wb")

        while True:
            tag, length = struct.unpack(">BI", sock.recv(5))

            if tag == T_FCHUNK:
                buffer = b""
                while len(buffer) < length:
                    buffer += sock.recv(length - len(buffer))
                file.write(buffer)

            elif tag == T_FEND:
                file.close()
                send_msg(sock, T_MSG, f"File {filename} has been uploaded.".encode())
                return True

    def handle_download(self, sock, filename):
        filepath = f"{self.root_dir}/{filename}"

        if os.path.isfile(filepath):
            send_msg(sock, T_FREADY, filename.encode())
            send_file(sock, filepath)
            return True
        else:
            send_msg(sock, T_FNOTFOUND, filename.encode())
            return False
    
    def broadcast_msg(self, message, exclude_sock=None):
        for client in self.clients:
            if client != exclude_sock:
                try:
                    send_msg(client, T_MSG, message.encode())
                except (OSError, ConnectionError):
                    pass

if __name__ == "__main__":
    server_port = int(input("Enter server's port: ").strip())
    root_dir = input("Enter server's root directory: ").strip() or os.path.expanduser('~')

    server = Server("127.0.0.1", server_port, root_dir)
    server.run()