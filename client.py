import socket
import struct
import os
import threading
import queue

class Client:
    def __init__(self, HOST, PORT, download_dir):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((HOST, PORT))
        self.socket.settimeout(10.0)

        print("Connected to server.")

        self.download_dir = os.path.expanduser(download_dir)
        self.running = True
        self.socket_read_lock = threading.Lock()
        self.response_queue = queue.Queue()

        listener_thread = threading.Thread(target=self.listen_for_messages, daemon=True)
        listener_thread.start()

        self.handle_command()

    def handle_command(self):
        try:
            while True:
                args = input().strip().split(maxsplit=1)

                if not args:
                    continue

                if args[0] in ['/upload', '/download'] and len(args) < 2:
                    print("Missing second argument.")
                    continue

                if args[0] == "/list":
                    self.list()
                elif args[0] == "/upload":
                    self.upload(args[1])                
                elif args[0] == "/download":
                    self.download(args[1])
                else:
                    print("Command unidentified.")
                    continue
        except KeyboardInterrupt:
            print("\nDisconnected by keyboard interrupt. Exiting...")
        finally:
            self.running = False
            self.socket.close()

    def recv_msg(self):
        try:
            return self.response_queue.get(timeout=5)
        except queue.Empty:
            return None
    
    def send_msg(self, data):
        header = struct.pack(">I", len(data))
        self.socket.sendall(header + data)
    
    def listen_for_messages(self):
        while self.running:
            if not self.socket_read_lock.acquire(timeout=0.1):
                continue
            
            try:
                msg = self._read_msg()
                if msg is None:
                    break
                
                decoded = msg.decode()
                if any(keyword in decoded for keyword in ["Client", "connected", "downloaded", "uploaded"]):
                    print(f"[SERVER] {decoded}")
                else:
                    self.response_queue.put(msg)
            except socket.timeout:
                continue
            except (ConnectionResetError, OSError):
                break
            finally:
                self.socket_read_lock.release()
    
    def _read_msg(self):
        try:
            header = self.socket.recv(4)
            if len(header) < 4:
                return None
            length = struct.unpack(">I", header)[0]
            buffer = b''
            while len(buffer) < length:
                buffer += self.socket.recv(length - len(buffer))
            return buffer
        except socket.timeout:
            raise
    
    def send_file(self, path, chunk_size=4096):
        with open(path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                self.socket.sendall(struct.pack(">I", len(chunk)) + chunk)
        self.socket.sendall(struct.pack(">I", 0))
    
    def recv_file(self, path):
        with open(path, "wb") as f:
            while True:
                try:
                    length = struct.unpack(">I", self.socket.recv(4))[0]
                except socket.timeout:
                    continue
                if length == 0:
                    break
                buffer = b""
                while len(buffer) < length:
                    try:
                        buffer += self.socket.recv(length - len(buffer))
                    except socket.timeout:
                        continue
                f.write(buffer)

    def list(self):
        self.send_msg(b"/list")
        data = self.recv_msg()
        print(data.decode(), end='')

    def upload(self, path):
        path = os.path.expanduser(path)
        with self.socket_read_lock:
            self.send_msg(f"/upload {os.path.basename(path)}".encode())
            self.send_file(path)
        
        resp = self.recv_msg()
        if resp:
            print(resp.decode(), end='')

    def download(self, filename):
        with self.socket_read_lock:
            self.send_msg(f"/download {filename}".encode())
            filepath = f"{self.download_dir}/{filename}"
            print(f"Downloading {filename}...")
            self.recv_file(filepath)

        print(f"File {filename} downloaded.")
        
        while True:
            try:
                msg = self.response_queue.get_nowait()
            except queue.Empty:
                break        

if __name__ == "__main__":
    server_ip = input("Enter server's IP: ").strip()
    server_port = int(input("Enter server's port: ").strip())
    download_dir = input("Enter download directory: ").strip() or os.getcwd()

    Client(server_ip, server_port, download_dir)