[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/mRmkZGKe)
# Network Programming - Assignment G01

## Anggota Kelompok
| Nama           | NRP        | Kelas     |
| ---            | ---        | ----------|
| Mohammed Lazuardi Yasfin | 5025241139 | C |
| Bintang Ilham Pabeta     | 5025241152 | C |

## Link Youtube (Unlisted)
Link ditaruh di bawah ini
```
https://youtu.be/MO_emYjdFM4
```

## Penjelasan Program

### Servers and Client

| File | Description |
| ---- | ----------- |
| [`server-sync.py`](#server-server-syncpy) | Serves one client at a time |
| [`server-select.py`](#server-server-selectpy) | Server w/ select module |
| [`server-poll.py`](#server-server-pollpy) | Server w/ poll syscall |
| [`server-thread.py`](#server-server-threadpy) | Server w/ threading module |
| [`client.py`](#client-clientpy) | Client program to handle download/upload |


#### Server: `server-sync.py`

Implementasi untuk synchronous server cukup sederhana karena server cukup melayani satu client dalam satu waktu. Berikut adalah potongan kode yang lumayan membedakan teknik ini dengan teknik-teknik lain.

```python
def start(self):
    try:
        while True:
            client_sock, client_addr = self.socket.accept()
            print(f"Connected by {client_addr}")
            
            while True:
                header = client_sock.recv(1)

                if not header:
                    client_sock.close()
                    print(f"Disconnected from {client_addr}")
                    break

                command = recv_msg(client_sock).decode()

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
```

Pada bagian `accept()`, program akan berhenti (blocking) dan menunggu sampai suatu client membuka koneksi dengan server. Setelah koneksi terjalin, program masuk ke infinite loop dimana program akan terus menerus menerima data sampai client menutup koneksi dengan server. Konsekuensi dari perilaku program ini adalah client lain yang terkoneksi setelah server telah terkoneksi harus menunggu di backlog server socket. Setiap payload yang dikirim oleh client tersebut akan diabaikan oleh server.

#### Server: `server-select.py`

Konsep utama dari select adalah I/O Multiplexing. Sederhananya, select memungkinkan server untuk "mengawasi" banyak koneksi sekaligus dalam satu thread tanpa harus menunggu (blocking) di salah satu koneksi saja.

1. **List pemantauan library select**

    Sebuah list bernama input_sockets sebagai "pintu" yang akan diawasi oleh select.

    ```py
    self.input_sockets = [self.server_socket]
    ```

2. **Fungsi Utama select.select()**
    
    ```py
    read_ready, _, _ = select.select(self.input_sockets, [], [])
    ```

    - Read list: Socket yang ingin kita pantau apakah ada data yang masuk.
    - Write list: Socket yang ingin kita pantau apakah siap menerima data.
    - Error list: Socket yang ingin kita pantau jika ada error.

3. **Membedakan Jenis Aktivitas**
    Setelah select memberitahu ada socket yang siap, kita melakukan perulangan for sock in read_ready untuk mengecek socket mana yang aktif. Ada dua kondisi utama:

    - **Jika yang aktif adalah server socket**
    
        Ada client baru yang mencoba terhubung (ingin melakukan handshake), maka kita terima koneksinya dengan .accept(), lalu masukkan socket klien baru tersebut ke dalam daftar input_sockets. Sekarang, select juga akan mengawasi data yang datang dari klien ini di putaran loop berikutnya.

        ```py
        if sock == self.server_socket:
            client_socket, client_addr = self.server_socket.accept()
            self.input_sockets.append(client_socket)
        ```

    - **Jika yang aktif adalah socket client (Existing Connection)**

        Client yang sudah terhubung sebelumnya sedang mengirimkan pesan/perintah, maka kita baca datanya. Jika data kosong (client disconnect), kita hapus socket tersebut dari daftar.

        ```py
        else:
            command_payload = self.recv_msg(sock)
        ```


#### Server: `server-poll.py`

Meskipun tujuannya sama (I/O Multiplexing), poll bekerja sedikit berbeda. Jika select menggunakan list socket, poll menggunakan File Descriptor (fd) dan Event Mask.

1. **Non-Blocking dan Poll Object**

    Berbeda dengan select standar, saat menggunakan poll, kita biasanya mengubah socket ke mode non-blocking.

    ```py
    self.server_socket.setblocking(False) # Jangan biarkan socket menunggu selamanya
    self.poll_object = select.poll()      # Membuat objek poll
    self.poll_object.register(self.server_socket.fileno(), select.POLLIN)
    ```

    - `.fileno()`: poll tidak bekerja dengan objek socket Python secara langsung, melainkan dengan nomor identitasnya di sistem operasi yang disebut File Descriptor (integer).
    - `.register()`: Kita mendaftarkan socket ke "buku pantauan" si poll.
    - `select.POLLIN`: Ini adalah Event Mask. Kita bilang ke poll: "Kabari saya kalau ada data masuk (input)".

2. **Pemetaan FD ke Objek Socket (`fd_map`)**
    
    Karena poll hanya mengembalikan nomor (integer), kita butuh kamus (dictionary) untuk mencari tahu "Nomor 5 ini milik socket yang mana?".
    
    ```py
    self.fd_map = {self.server_socket.fileno(): self.server_socket}
    ```

3. **Loop Utama dan Event Checking**
    
    Program akan berhenti di .poll() sampai ada aktivitas. 

    ```py
    for fd, event in self.poll_object.poll():
        sock = self.fd_map[fd] # Ambil objek socket berdasarkan nomornya
    ```

    Di sini, poll mengembalikan pasangan (fd, event). Kita melakukan pengecekan event menggunakan bitwise operator (&):

    - **Event POLLIN (Data Masuk / Koneksi Baru)**

        Sama seperti select, jika server socket yang aktif, berarti ada koneksi baru. Jika client socket yang aktif, berarti ada pesan masuk.

        ```py
        if event & select.POLLIN:
            if sock == self.server_socket:
                # Ada client baru -> .accept() -> .register() ke poll
            else:
                # Ada data dari client -> .recv_msg()
        ```

    - **Event POLLOUT (Siap Kirim Data)**

        Ini fitur di poll, kita bisa tahu kapan OS siap mengirimkan data keluar tanpa membuat program kita stuck.
        
        ```py
        elif event & select.POLLOUT:
            # Ambil data dari buffer, kirim pakai .send()
            # Jika sudah selesai kirim, kembali ke state POLLIN
            self.poll_object.modify(sock.fileno(), select.POLLIN)
        ```
        
        - `.modify()`: Kita mengubah status pantauan. "Saya sudah selesai kirim data, sekarang pantau data masuk lagi ya".

    - **Event Error (POLLHUP, POLLERR, POLLNVAL)**

        Poll sangat eksplisit dalam menangani masalah koneksi.

        - `POLLHUP`: Client memutus koneksi (Hang up).
        - `POLLERR`: Terjadi error di tingkat socket.
        - `unregister()`: Jika ada error, kita hapus nomor fd dari daftar pantauan.    

#### Server: `server-thread.py`

Dengan menggunakan modul threading, menangani beberapa client sekaligus dapat dilakukan dengan cara spawning thread untuk setiap client baru Untuk melakukan spawning thread baru, digunakan metode target function with arguments sebagai berikut.
```python
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
```

List `clients` digunakan untuk menyimpan informasi client yang masih terkoneksi. Setiap client baru akan dimasukkan ke dalam list tersebut dan kemudian diberikan suatu thread khusus. Setiap thread yang di-spawn akan langsung menjalankan fungsi `handle_new_client()` yang kurang lebih berisi logika yang sama seperti teknik lain. Apabila client memutus koneksi, yang mana client akan mengirimkan empty packet, fungsi tersebut akan menghapus client dari list dan memutus socket client pada server.

Perlu diketahui bahwa call `accept()` pada potongan tersebut masih melakukan blocking. Berbeda dengan I/O multiplexing, hal ini tidak mengganggu paralelisme karena masing-masing client punya satu client socket pada server dan berjalan secara independen. 


#### Client: `client.py`

Secara umum, seharusnya implementasi client cukup simpel dan dapat dilakukan secara synchronous. Namun, kebutuhan akan broadcast tidak dapat dipenuhi hanya dengan pendekatan synchronous. Untuk itu, pada file `client.py` diimplementasikan threading, yakni satu main thread yang bertugas untuk handling input command dan satu thread tambahan yang bertanggung jawab penuh atas receiving payload. 

Perhatikan definisi method `__init__` berikut. Seketika instance `Client` dibuat, program langsung membuat thread yang memanggil method `receive_all` yang bertugas untuk blocking `recv()` setiap data yang dikirimkan. Setelah pembuatan thread dan kemudian dijalankan, program akan memanggil method `handle_command()` yang berisi logika untuk handling input command. 
```python
def __init__(self, HOST, PORT, download_dir):
    self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self.socket.connect((HOST, PORT))

    self.download_dir = os.path.expanduser(download_dir)
    self.running = True

    threading.Thread(target=self.receive_all, daemon=True).start()

    self.handle_command()
```

Seketika user menginputkan suatu command yang valid, `handle_command()` langsung melakukan parsing terhadap input dan mengirimkannya sebagai payload terhadap server. Logika ini terus menerus berjalan hingga program menerima exception `KeyboardInterrupt`.
```python
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
```

Pada `receive_all()`, dilakukan blocking `recv()` dimana setiap payload diekstrak dari header tag. Berdasarkan nilai `tag` ini, client dapat memastikan penanganan mana yang sesuai untuk jenis payload tertentu.
```python
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
            filename = self.recv_msg().decode()
            print(f"{filename} does not exist on the server.")
            filename = ''

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
```



### Features

| Client Commands | Description |
| -------- | ----------- |
| [`/list`](#client-command-list) | List existing file on the server |
| [`/upload <filename>`](#client-command-upload-filename) | Uploads a file into the server |
| [`/download <filename>`](#client-command-download-filename) | Download a file from the server |

#### Feature: Broadcast

Mekanisme broadcast dalam `server-*.py` memungkinkan server untuk mengirimkan informasi kepada seluruh client yang sedang terhubung secara real-time. Hal ini krusial untuk menciptakan interaksi antar-pengguna dalam arsitektur multi-client.

1. Fungsi Utama: `broadcast_msg`

    Fungsi ini adalah inti dari mekanisme penyebaran pesan. Server akan mengiterasi daftar client yang aktif dan mengirimkan pesan.

    ```py
    def broadcast_msg(self, message, exclude_sock=None):
        for client in self.clients:
            if client != exclude_sock:
                try:
                    msg_encoded = message.encode()
                    # Mengikuti protokol 4-byte header
                    header = struct.pack(">I", len(msg_encoded))
                    client.sendall(header + msg_encoded)
                except (OSError, ConnectionError):
                    pass # Menangani client yang mungkin sudah terputus secara tiba-tiba
    ```

2. Kapan Broadcast Dipicu?
    
    Server menggunakan broadcast pada tiga momen penting untuk memberikan transparansi aktivitas di dalam server:

    - Saat Client Baru Terhubung
        
        Memberitahu semua pengguna lama bahwa ada anggota baru yang masuk ke jaringan.

        ```py
        if sock == self.server_socket:
            conn, addr = self.server_socket.accept()
            # ... (proses registrasi client)
            self.broadcast_msg(f"Client {addr} has connected.", exclude_sock=conn)
        ```

    - Notifikasi Berhasil Download
        
        Memberikan informasi kepada pengguna lain mengenai file yang sedang didownload.

        ```py
        if message.startswith("/download "):
            # ... (proses pengiriman file)
            self.broadcast_msg(f"Client {sock.getpeername()} has successfully downloaded {filename}", exclude_sock=sock)
        ```

    - Notifikasi Berhasil Upload

        Sangat penting agar pengguna lain tahu bahwa ada file baru yang tersedia di server dan siap untuk di-list atau di-download.

        ```py
        if message.startswith("/upload "):
            if self.handle_upload(sock, filename):
                self.broadcast_msg(f"Client {sock.getpeername()} has uploaded {filename}", exclude_sock=sock)
        ```


#### Client Command: `/list`

Berikut adalah logika server untuk handling command list.

```python
def handle_list(self, sock):
    filenames = []
    
    with os.scandir(self.root_dir) as entries:
        for entry in entries:
            if entry.is_file():
                filenames.append(entry.name)

    send_msg(sock, T_MSG, ("\n".join(filenames) + "\n").encode())
```

Karena permintaan tugas adalah mendaftar semua file yang ada di server, logikanya menjadi cukup sederhana. Menggunakan bantuan module `os`, `scandir()` dapat digunakan untuk mendapatkan iterables berupa seluruh entri yang ada di dalam suatu direktori. Iterables kemudian dipilah sehingga hanya diambil nama entri dari suatu file saja. Hasil pemilihan akan menghasilkan array `filenames` yang selanjutnya dijadikan payload untuk dikirimkan ke client.

```python
def send_msg(sock, tag, data):
    header = struct.pack(">BI", tag, len(data))
    sock.sendall(header + data)
```

Fungsi `send_msg()` di atas ini akan membungkus payload dengan tipe payload dan panjang data dan kemudian dikirimkan secara keseluruhan. Alasan dari penggunaan fixed-length header disini adalah karena payload yang dikirim dapat dipastikan tidak terlalu besar, sehingga tidak terlalu meningkatkan kompleksitas kode.

Dari sisi client, client mengirim payload command terlebih dahulu lalu dilayani oleh server. Dilanjutkan dengan blocking `recv()` sampai data diterima seutuhnya. Karena tidak terdapat informasi yang jelas terkait implementasi list, diasumsikan perintah `/list` ini akan mendaftar seluruh file yang ada di direktori root yang sudah ditentukan saat inisialisasi objek `Server`.

Dari sisi client, pada main thread, client mengirim payload command terlebih dahulu yang kemudian akan dilayani oleh server. Pada thread client yang bertugas sebagai receiver akan menangkap payload list yang dikirim oleh server dan kemudian dilakukan print pada terminal client.
```python
self.send_msg(b"/list")
```

```python
while self.running:
    header = self.socket.recv(1)
    
    if not header: 
        break

    tag, = struct.unpack(">B", header)

    if tag == T_MSG:
        msg = self.recv_msg()
        print(msg.decode())
```

Pada fungsi `recv_msg()` diterapkan mekanisme unpacking fixed-length header sebagai berikut.
```python
def recv_msg(self):
    header = self.socket.recv(4)
    length = struct.unpack(">I", header)[0]
    
    buffer = b''
    while len(buffer) < length:
        buffer += self.socket.recv(length - len(buffer))

    return buffer
```

#### Client Command: `/upload <filename>`

Berikut adalah logika untuk handling command upload dari sisi server. Sesuai dengan permintaan tugas, command upload hanya akan mengirimkan payload filename, sehingga cukup diasumsikan apabila client mengirimkan file yang ada pada relative path program client berjalan.
```python
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
```

Dapat diperhatikan pada potongan kode di atas, fungsi tersebut akan terus menerus melakukan blocking sampai pada akhirnya diterima payload yang menunjukkan akhir dari pengiriman file. Penentuan jenis payload didasarkan pada header awal yang berisi tag payload yang diterima.

Dari sisi client, input dari user akan diparse lalu dikirimkan sebagai payload. Sebelum pengiriman, sisi client harus memastikan apakah file yang akan di-upload memang benar adanya. Jika tidak, maka dilakukan print error.
```python
elif args[0] == "/upload":
    filename = os.path.basename(args[1])
    if os.path.isfile(filename):
        self.send_msg(f"/upload {filename}".encode())
        self.send_file(filename)    
    else:
        print(f"File {filename} does not exist.")
```

Pengiriman file besar dari client ke server cukup berisiko tinggi. Oleh karena itu, pada client, `send_file()` diimplementasikan dengan chunked blocks header. Dengan demikian, file besar tidak seutuhnya disimpan dalam memori terlebih dahulu sebelum pengiriman, yang mana dapat meningkatkan reliabilitas pengiriman.
```python
def send_file(self, path, chunk_size=4096):
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            self.socket.sendall(struct.pack(">BI", T_FCHUNK, len(chunk)) + chunk)
    self.socket.sendall(struct.pack(">BI", T_FEND, 0))
```
Perhatikan juga pada setiap pemanggilan mehod `sendall()`. Setiap payload yang dikirimkan juga dibungkus dengan tag payload. `T_FCHUNK` menunjukkan bahwa payload merupakan bagian dari suatu data, sementara `T_FEND` menunjukkan bahwa pengiriman file selesai secara sempurna.

#### Client Command: `/download <filename>`

Berikut adalah logika download dari sisi server. Kurang lebih mirip dengan logika upload dari sisi client. Perbedaan utamanya disini, tidak mudah untuk memberi tahu client apabila file yang diminta ternyata tidak terdapat di server. Salah satu handling yang paling masuk akal adalah dengan menggunakan tag payload yang menunjukkan error file tidak dapat ditemukan.
```python
def handle_download(self, sock, filename):
    filepath = f"{self.root_dir}/{filename}"

    if os.path.isfile(filepath):
        send_msg(sock, T_FREADY, filename.encode())
        send_file(sock, filepath)
        return True
    else:
        send_msg(sock, T_FNOTFOUND, filename.encode())
        return False
```

Dari sisi client logikanya lumayan panjang, tetapi pada intinya cukup sederhana. CLient yang berjalan memiliki dua thread yang masing-masing bertanggung jawab atas operasi send dan receive. Thread yang bertugas atas receiver akan menangkap seluruh payload yang dikirimkan oleh server dan menentukan handling yang sesuai berdasarkan tag payloadnya. Khusus command download, dibutuhkan empat tag, antara lain `T_FREADY`, `T_FCHUNK`, `T_FNOTFOUND`, dan `T_FEND`. Tag `T_FREADY` dan `T_FNOTFOUND` penting untuk memastikan terlebih dahulu apakah file memang benar ada di server.
```python    
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
            filename = self.recv_msg().decode()
            print(f"{filename} does not exist on the server.")
            filename = ''

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
```
Secara implementasi handling kurang lebih sama seperti bagaimana cara menyimpan file hasil upload dari sisi server.

## Screenshot Hasil

- Download:

    ![](/assets/download.gif)

- Upload:

    ![](/assets/upload.gif)