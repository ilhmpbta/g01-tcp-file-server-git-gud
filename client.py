import socket
import struct
import os
import threading

T_FREADY = 0x10
T_FCHUNK = 0x11
T_FEND = 0x12
T_FNOTFOUND = 0x19
T_MSG = 0x21

class Client:
    def __init__(self, HOST, PORT, download_dir):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((HOST, PORT))

        self.download_dir = os.path.expanduser(download_dir)
        self.running = True

        threading.Thread(target=self.receive_all, daemon=True).start()

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
                    self.send_msg(b"/list")
                elif args[0] == "/upload":
                    filename = os.path.basename(args[1])
                    if os.path.isfile(filename):
                        self.send_msg(f"/upload {filename}".encode())
                        self.send_file(filename)    
                    else:
                        print(f"File {filename} does not exist.")
                elif args[0] == "/download":
                    self.send_msg(f"/download {os.path.basename(args[1])}".encode())
                else:
                    print("Command unidentified.")
                    continue
        except KeyboardInterrupt:
            print("\nDisconnected by keyboard interrupt. Exiting...")
        finally:
            self.socket.close()
    
    def receive_all(self):
        filename = ''
        filepath = ''
        file = None

        while self.running:
            header = self.socket.recv(1)
            
            if not header: 
                break

            tag, = struct.unpack(">B", header)

            if tag == T_MSG:
                msg = self.recv_msg()
                print(msg.decode())

            elif tag == T_FREADY:
                filename = self.recv_msg().decode()
                print(f"Server is ready to send {filename}.")
                filepath = os.path.join(self.download_dir, filename)
                file = open(filepath, "wb")

            elif tag == T_FNOTFOUND:
                print(f"{filename} does not exist on the server.")

            elif tag == T_FCHUNK:
                print(f"Downloading {filename}...")
                length = struct.unpack(">I", self.socket.recv(4))[0]
                buffer = b""
                while len(buffer) < length:
                    buffer += self.socket.recv(length - len(buffer))
                file.write(buffer)

            elif tag == T_FEND:
                if file:
                    file.close()
                    file = None
                print(f"{filename} downloaded")
                filename = ''
                filepath = ''

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

    def recv_msg(self):
        header = self.socket.recv(4)
        length = struct.unpack(">I", header)[0]
        
        buffer = b''
        while len(buffer) < length:
            buffer += self.socket.recv(length - len(buffer))

        return buffer
    
    def send_msg(self, data):
        header = struct.pack(">BI", T_MSG, len(data))
        self.socket.sendall(header + data)
    
    def send_file(self, path, chunk_size=4096):
        with open(path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                self.socket.sendall(struct.pack(">BI", T_FCHUNK, len(chunk)) + chunk)
        self.socket.sendall(struct.pack(">BI", T_FEND, 0))

if __name__ == "__main__":
    server_ip = input("Enter server's IP: ").strip()
    server_port = int(input("Enter server's port: ").strip())
    download_dir = input("Enter download directory: ").strip() or os.getcwd()

    Client(server_ip, server_port, download_dir)