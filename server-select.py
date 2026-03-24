import socket, select, os, struct

class Server:
    def __init__(self, host, port, root_dir="~/workspace/college/progjar/g01-tcp-file-server-git-gud"):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((host, port))
        self.server_socket.listen(5)
        self.input_sockets = [self.server_socket]
        self.root_dir = os.path.expanduser(root_dir)

        while True:
            read_ready, _, _ = select.select(self.input_sockets, [], [])

            for sock in read_ready:
                if sock == self.server_socket:
                    client_socket, client_addr = self.server_socket.accept()
                    self.input_sockets.append(client_socket)
                    print(f"Connected: {client_addr}")
                else:
                    try:
                        command_payload = self.recv_msg(sock)
                        if command_payload is None:
                            print(f"Connection closed by {sock.getpeername()}")
                            self.input_sockets.remove(sock)
                            sock.close()
                            continue

                        message = command_payload.decode().strip()
                        print(f"Received data: {message} from {sock.getpeername()}")
                                
                        if message == "/list":
                            files = self.list_files()
                            payload = ("\n".join(files) + "\n").encode() if files else b"(empty)\n"
                            self.send_msg(sock, payload)
                            continue

                        if message.startswith("/download "):
                            filename = message.split(maxsplit=1)[1].strip()
                            self.handle_download(sock, filename)
                            continue

                        if message == "/download":
                            resp = "Usage: /download <filename>\n"
                            self.send_msg(sock, resp.encode())
                            continue

                        if message.startswith("/upload "):
                            filename = message.split(maxsplit=1)[1].strip()
                            self.handle_upload(sock, filename)
                            resp = "upload: upload successful!\n"
                            self.send_msg(sock, resp.encode())
                            continue

                        if message == "/upload":
                            resp = "Usage: /upload <filename>\n"
                            self.send_msg(sock, resp.encode())
                            continue

                        resp = "Unknown command.\n"
                        self.send_msg(sock, resp.encode())
                            
                    except (ConnectionResetError, OSError) as e:
                        print(f"Connection error: {e}")
                        if sock in self.input_sockets:
                            self.input_sockets.remove(sock)
                        sock.close()

    def send_msg(self, sock, data):
        header = struct.pack(">I", len(data))
        sock.sendall(header + data)

    def recv_msg(self, sock):
        header = sock.recv(4)

        if len(header) < 4:
            return None

        length = struct.unpack(">I", header)[0]

        buffer = b''
        while len(buffer) < length:
            buffer += sock.recv(length - len(buffer))

        return buffer

    def list_files(self):
        filenames = []
        with os.scandir(self.root_dir) as entries:
            for entry in entries:
                if entry.is_file():
                    filenames.append(entry.name)
        return filenames

    def handle_upload(self, sock, filename):
        file_path = os.path.join(self.root_dir, filename)

        with open(file_path, "wb") as f:
            while True:
                header = sock.recv(4)
                if len(header) < 4:
                    break
                chunk_size = struct.unpack(">I", header)[0]
                if chunk_size == 0:
                    break
                chunk = sock.recv(chunk_size)
                f.write(chunk)

    def handle_download(self, sock, filename):
        filepath = os.path.join(self.root_dir, filename)
        if not os.path.isfile(filepath):
            sock.sendall(struct.pack(">I", 0))
        else:
            with open(filepath, "rb") as f:
                while True:
                    chunk = f.read(4096)
                    if not chunk:
                        break
                    sock.sendall(struct.pack(">I", len(chunk)) + chunk)
            sock.sendall(struct.pack(">I", 0))

if __name__ == "__main__":
    server = Server('127.0.0.1', 6767)