import socket, select

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

HOST = '127.0.0.1'
PORT = 5000

server_socket.bind((HOST, PORT))
server_socket.listen(5)
input_sockets = [server_socket]
server_socket.setblocking(False)

poll_object = select.poll()
poll_object.register(server_socket.fileno(), select.POLLIN)

fd_map = {server_socket.fileno(): server_socket}
send_buffers = {}

while True:
    try:
        for fd, event in poll_object.poll():
            sock = fd_map[fd]

            if sock == server_socket:
                conn, addr = server_socket.accept()
                conn.setblocking(False)
                fd_map[conn.fileno()] = conn
                poll_object.register(conn.fileno(), select.POLLIN)
                print(f"Connected: {addr}")
            
            elif event & select.POLLIN:
                data = sock.recv(4096)
                if not data:
                    poll_object.unregister(sock.fileno())
                    print(f"Connection closed by {sock.getpeername()}")
                    del fd_map[sock.fileno()]
                    sock.close()
                else:
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

                    send_buffers[sock.fileno()] = response.encode()
                    poll_object.modify(sock.fileno(), select.POLLOUT)
            
            elif event & select.POLLOUT:
                data = send_buffers.pop(sock.fileno())
                n = sock.send(data)
                if n < len(data):
                    send_buffers[sock.fileno()] = data[n:]
                else:
                    poll_object.modify(sock.fileno(), select.POLLIN)

            if event & (select.POLLHUP | select.POLLERR | select.POLLNVAL):
                poll_object.unregister(sock.fileno())
                print(f"Connection error with {sock.getpeername()}")
                del fd_map[sock.fileno()]
                sock.close()
    
    except (ConnectionResetError, KeyboardInterrupt):
        poll_object.unregister(sock.fileno())
        print(f"Connection reset by {sock.getpeername()}")
        del fd_map[sock.fileno()]
        sock.close()