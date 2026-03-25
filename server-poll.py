import socket, select, os, struct

T_FREADY = 0x10
T_FCHUNK = 0x11
T_FEND = 0x12
T_FNOTFOUND = 0x19
T_MSG = 0x21

class Server:
    def __init__(self, host, port, root_dir="~/workspace/college/progjar/g01-tcp-file-server-git-gud"):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((host, port))
        self.server_socket.listen(5)
        self.root_dir = os.path.expanduser(root_dir)
        self.server_socket.setblocking(False)

        self.poll_object = select.poll()
        self.poll_object.register(self.server_socket.fileno(), select.POLLIN)

        self.fd_map = {self.server_socket.fileno(): self.server_socket}
        self.send_buffers = {}
        self.clients = []

        while True:
            for fd, event in self.poll_object.poll():
                try:
                    sock = self.fd_map[fd]

                    if sock == self.server_socket:
                        conn, addr = self.server_socket.accept()
                        conn.setblocking(False)
                        self.fd_map[conn.fileno()] = conn
                        self.poll_object.register(conn.fileno(), select.POLLIN)
                        self.clients.append(conn)
                        print(f"Connected: {addr}")
                        self.broadcast_msg(f"Client {addr} has connected.", exclude_sock=conn)
                    
                    elif event & select.POLLIN:
                        command_payload = self.recv_msg(sock)
                        if command_payload is None:
                            if sock in self.clients:
                                self.clients.remove(sock)
                            self.poll_object.unregister(sock.fileno())
                            print(f"Connection closed by {sock.getpeername()}")
                            del self.fd_map[sock.fileno()]
                            sock.close()
                            continue

                        message = command_payload.decode().strip()
                        print(f"Received data: {message} from {sock.getpeername()}")

                        if message == "/list":
                            files = self.list_files()
                            payload = ("\n".join(files) + "\n").encode() if files else b"(empty)\n"
                            self.send_buffers[sock.fileno()] = struct.pack(">BI", T_MSG, len(payload)) + payload
                            self.poll_object.modify(sock.fileno(), select.POLLOUT)
                            continue

                        if message.startswith("/download "):
                            filename = message.split(maxsplit=1)[1].strip()
                            filepath = os.path.join(self.root_dir, filename)

                            if not os.path.isfile(filepath):
                                self.send_buffers[sock.fileno()] = struct.pack(">B", T_FNOTFOUND)
                            else:
                                buffer = struct.pack(">BI", T_FREADY, len(filename)) + filename.encode()
                                with open(filepath, "rb") as f:
                                    while True:
                                        chunk = f.read(4096)
                                        if not chunk:
                                            break
                                        buffer += struct.pack(">BI", T_FCHUNK, len(chunk)) + chunk
                                buffer += struct.pack(">B", T_FEND)
                                self.send_buffers[sock.fileno()] = buffer
                                self.broadcast_msg(f"Client {sock.getpeername()} has successfully downloaded {filename}", exclude_sock=sock)

                            self.poll_object.modify(sock.fileno(), select.POLLOUT)
                            continue

                        if message == "/download":
                            resp = "Usage: /download <filename>\n".encode()
                            self.send_buffers[sock.fileno()] = struct.pack(">BI", T_MSG, len(resp)) + resp
                            self.poll_object.modify(sock.fileno(), select.POLLOUT)
                            continue

                        if message.startswith("/upload "):
                            filename = message.split(maxsplit=1)[1].strip()
                            sock.setblocking(True)
                            if self.handle_upload(sock, filename):
                                resp = "upload: upload successful!\n".encode()
                                self.broadcast_msg(f"Client {sock.getpeername()} has uploaded {filename}", exclude_sock=sock)
                            else:
                                resp = "upload: upload failed!\n".encode()
                            sock.setblocking(False)
                            self.send_buffers[sock.fileno()] = struct.pack(">BI", T_MSG, len(resp)) + resp
                            self.poll_object.modify(sock.fileno(), select.POLLOUT)
                            continue

                        if message == "/upload":
                            resp = "Usage: /upload <filename>\n".encode()
                            self.send_buffers[sock.fileno()] = struct.pack(">BI", T_MSG, len(resp)) + resp
                            self.poll_object.modify(sock.fileno(), select.POLLOUT)
                            continue

                        resp = "Unknown command.\n".encode()
                        self.send_buffers[sock.fileno()] = struct.pack(">BI", T_MSG, len(resp)) + resp
                        self.poll_object.modify(sock.fileno(), select.POLLOUT)
                    
                    elif event & select.POLLOUT:
                        data = self.send_buffers.pop(sock.fileno())
                        n = sock.send(data)
                        if n < len(data):
                            self.send_buffers[sock.fileno()] = data[n:]
                        else:
                            self.poll_object.modify(sock.fileno(), select.POLLIN)

                    if event & (select.POLLHUP | select.POLLERR | select.POLLNVAL):
                        if sock in self.clients:
                            self.clients.remove(sock)
                        self.poll_object.unregister(sock.fileno())
                        print(f"Connection error with {sock.getpeername()}")
                        del self.fd_map[sock.fileno()]
                        sock.close()
                
                except (ConnectionResetError, OSError) as e:
                    if fd in self.fd_map:
                        sock = self.fd_map[fd]
                        if sock in self.clients:
                            self.clients.remove(sock)
                        if sock.fileno() >= 0:
                            self.poll_object.unregister(sock.fileno())
                        print(f"Connection error: {e}")
                        del self.fd_map[fd]
                        sock.close()

    def send_msg(self, sock, data, tag=T_MSG):
        header = struct.pack(">BI", tag, len(data))
        sock.sendall(header + data)
    
    def broadcast_msg(self, message, exclude_sock=None):
        for client in self.clients:
            if client != exclude_sock:
                try:
                    msg_encoded = message.encode()
                    self.send_msg(client, msg_encoded)
                except (OSError, ConnectionError):
                    pass

    def recv_msg(self, sock):
        tag_header = sock.recv(1)
        if len(tag_header) < 1:
            return None

        length_header = sock.recv(4)
        if len(length_header) < 4:
            return None

        length = struct.unpack(">I", length_header)[0]

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
        try:
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
            return True
        except (OSError, IOError):
            return False

    def handle_download(self, sock, filename):
        filepath = os.path.join(self.root_dir, filename)
        if not os.path.isfile(filepath):
            return b"File does not exist.\n"

        with open(filepath, "rb") as f:
            return f.read()

if __name__ == "__main__":
    Server('127.0.0.1', 6767)