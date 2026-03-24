import socket
import struct
import os

class Client:
    def __init__(self, HOST, PORT, download_dir="~"):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((HOST, PORT))

        print("Connected to server.")

        self.download_dir = os.path.expanduser(download_dir)

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
            self.socket.close()

    def recv_msg(self):
        header = self.socket.recv(4)

        if len(header) < 4:
            return None

        length = struct.unpack(">I", header)[0]

        buffer = b''
        while len(buffer) < length:
            buffer += self.socket.recv(length - len(buffer))

        return buffer
    
    def send_msg(self, data):
        header = struct.pack(">I", len(data))
        self.socket.sendall(header + data)
    
    def send_file(self, path, chunk_size=4096):
        pass
    
    def recv_file(self, path):
        with open(path, "wb") as f:
            while True:
                length = struct.unpack(">I", self.socket.recv(4))[0]
                if length == 0:
                    break
                buffer = b""
                while len(buffer) < length:
                    buffer += self.socket.recv(length - len(buffer))
                f.write(buffer)

    def list(self):
        self.send_msg(b"/list")
        data = self.recv_msg()
        print(data.decode())

    def upload(self, path):
        pass
            
    def download(self, filename):
        self.send_msg(f"/download {filename}".encode())
        filepath = f"{self.download_dir}/{filename}"

        print(f"Downloading {filename}...")

        self.recv_file(filepath)

        print(f"File {filename} downloaded.")
        

if __name__ == "__main__":
    # server_ip = input("Enter server's IP: ").strip()
    # server_port = int(input("Enter server's port: ").strip())

    server_ip = '127.0.0.1'
    server_port = 6767

    Client(server_ip, server_port)