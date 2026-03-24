import socket
import struct
import os

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
    def __init__(self, HOST, PORT, root_dir):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((HOST, PORT))
        self.socket.listen()

        self.root_dir = os.path.expanduser(root_dir)

    def start(self):
        try:
            while True:
                client_sock, client_addr = self.socket.accept()

                print(f"Connected by {client_addr}")
                while True:
                    data = recv_msg(client_sock)
                    if not data:
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
        except KeyboardInterrupt:
            self.socket.close()

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
    server_port = int(input("Enter server's port: ").strip())
    root_dir = input("Enter server's root directory: ").strip() or os.path.expanduser('~')

    server = Server("127.0.0.1", server_port, root_dir)
    server.start()