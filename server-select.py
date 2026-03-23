import socket, select

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

HOST = '127.0.0.1'
PORT = 5000

server_socket.bind((HOST, PORT))
server_socket.listen(5)
input_sockets = [server_socket]

while True:
    read_ready, _, _ = select.select(input_sockets, [], [])

    for sock in read_ready:
        if sock == server_socket:
            client_socket, client_addr = server_socket.accept()
            input_sockets.append(client_socket)
            print(f"Connected: {client_addr}")
        else:
            try:
                data = sock.recv(1024)
                if data:
                    message = data.decode()
                    print(f"Received data: {message} from {sock.getpeername()}")

                    if message == "/list\n":
                        # handle list via list.py
                        response = "list: list of items...\n"
                    elif message == "/download\n":
                        # handle download via download.py
                        response = "download: file content...\n"
                    elif message == "/upload\n":
                        # handle upload via upload.py
                        response = "upload: upload successful!\n"
                    else: response = "Unknown command.\n"

                    sock.sendall(response.encode())
                    
                else:
                    print(f"Connection closed by {sock.getpeername()}")
                    input_sockets.remove(sock)
                    sock.close()
            except (ConnectionResetError, KeyboardInterrupt):
                print(f"Connection reset by {sock.getpeername()}")
                input_sockets.remove(sock)
                sock.close()