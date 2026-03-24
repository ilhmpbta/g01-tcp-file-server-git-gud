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
```

Pada bagian `accept()`, program akan berhenti (blocking) dan menunggu sampai suatu client membuka koneksi dengan server. Setelah koneksi terjalin, program masuk ke infinite loop dimana program akan terus menerus menerima data sampai client menutup koneksi dengan server. Konsekuensi dari perilaku program ini adalah client lain yang terkoneksi setelah server telah terkoneksi harus menunggu di backlog server socket. Setiap payload yang dikirim oleh client tersebut akan diabaikan oleh server.

#### Server: `server-select.py`

> Before we start our work, let's say  
> أَعُوذُ بِاللَّهِ مِنَ الشَّيْطَانِ الرَّجِيمِ

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

> Before we start our work, let's say  
> أَعُوذُ بِاللَّهِ مِنَ الشَّيْطَانِ الرَّجِيمِ

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
            print(f"Connected by {client_addr}")

            client = {'client_socket': client_sock, 'client_addr': client_addr}

            self.clients.append(client)
            Thread(target = self.handle_new_client, args=(client,)).start()                    
    except KeyboardInterrupt:
        self.socket.close()

        for client in self.clients:
            client['client_socket'].close()

def handle_new_client(self, client):
    client_sock = client['client_socket']
    running = 1
    while running:
        data = recv_msg(client_sock)

        if not data:
            self.clients.remove(client)
            client_sock.close()
            running = 0
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
```

List `clients` digunakan untuk menyimpan informasi client yang masih terkoneksi. Setiap client baru akan dimasukkan ke dalam list tersebut dan kemudian diberikan suatu thread khusus. Setiap thread yang di-spawn akan langsung menjalankan fungsi `handle_new_client()` yang kurang lebih berisi logika yang sama seperti teknik lain. Apabila client memutus koneksi, yang mana client akan mengirimkan empty packet, fungsi tersebut akan menghapus client dari list dan memutus socket client pada server.

Perlu diketahui bahwa call `accept()` pada potongan tersebut masih melakukan blocking. Berbeda dengan I/O multiplexing, hal ini tidak mengganggu paralelisme karena masing-masing client punya satu client socket pada server dan berjalan secara independen. 


#### Client: `client.py`

Dokumen ini menjelaskan arsitektur internal dari client.py, dengan fokus pada bagaimana aplikasi menangani pesan secara asinkron menggunakan threading dan bagaimana ia mengelola aliran data (file passing) secara aman.

1. **Mekanisme Threading untuk Listening Broadcast**

    Client perlu mendengarkan pesan dari server (seperti notifikasi "User joined" atau pesan chat) sambil tetap menunggu input perintah dari pengguna. Untuk mencapai ini, client.py memisahkan tugas tersebut ke dalam thread yang berbeda.

    ```python
    # Inisialisasi thread di dalam __init__
    self.socket_read_lock = threading.Lock()
    listener_thread = threading.Thread(target=self.listen_for_messages, daemon=True)
    listener_thread.start()
    ```

    - Sinkronisasi menggunakan lock & queue
        
        Karena dua thread (Thread Utama dan Thread Listener) berbagi satu koneksi yang sama, risiko terjadinya collision sangat besar. Maka kita gunakan readlock dan queue

        ```py
        def listen_for_messages(self):
            while self.running:
                # Mencoba mendapatkan akses ke socket dengan timeout agar tidak deadlock
                if not self.socket_read_lock.acquire(timeout=0.1):
                    continue
                try:
                    msg = self._read_msg()
                    if msg is None: break
                    
                    # Jika pesan berisi kata kunci tertentu, langsung cetak (Notifikasi)
                    # Jika tidak, masukkan ke antrean (Data Respon)
                    self.response_queue.put(msg)
                finally:
                    self.socket_read_lock.release()
        ```

        - Socket Read Lock: Digunakan untuk memastikan hanya satu thread yang membaca dari socket pada satu waktu.
        - Response Queue: Jika pesan yang masuk bukan notifikasi umum, pesan tersebut disimpan dalam antrean (Queue) agar bisa diambil oleh thread utama saat dibutuhkan.

2. **Peran Client dalam Passing File**

    client.py bertanggung jawab untuk memastikan file yang dikirim (upload) atau diterima (download) tidak rusak dan sampai secara utuh melalui jaringan.

    - Protokol Header (Framing)

        ```py
        def send_msg(self, data):
            # Mengemas panjang data ke dalam 4 byte (Big-endian unsigned int)
            header = struct.pack(">I", len(data))
            self.socket.sendall(header + data)
        ```

    - File Chunking

        ```py
        def send_file(self, path, chunk_size=4096):
            with open(path, "rb") as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk: 
                        break # Selesai membaca file
                    
                    # Kirim setiap potongan dengan header panjangnya
                    self.socket.sendall(struct.pack(">I", len(chunk)) + chunk)
                    
            # Sinyal Selesai: Mengirim header dengan panjang 0
            self.socket.sendall(struct.pack(">I", 0))
        ```

3. **Safety**
    - Eksklusivitas Socket: Saat melakukan upload atau download, thread utama memegang socket_read_lock secara penuh. Ini menghentikan sementara thread pendengar agar byte-byte file tidak tertukar dengan pesan teks biasa.

    - Pembersihan Queue: Setelah download selesai, client membersihkan sisa pesan di response_queue untuk memastikan kondisi state client kembali bersih sebelum menerima perintah berikutnya.

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

    send_msg(sock, ("\n".join(filenames) + "\n").encode())
```

Karena permintaan tugas adalah mendaftar semua file yang ada di server, logikanya menjadi cukup sederhana. Menggunakan bantuan module os, scandir dapat digunakan untuk mendapatkan iterables berupa seluruh entri yang ada di dalam suatu direktori. Iterables kemudian dipilah sehingga hanya diambil nama entri dari suatu file saja. Hasil pemilihan akan menghasilkan array `filenames` yang selanjutnya dijadikan payload untuk dikirimkan ke client.

```python
def send_msg(sock, data):
    header = struct.pack(">I", len(data))
    sock.sendall(header + data)
```

Fungsi `send_msg()` di atas ini akan membungkus payload dengan panjang data dan kemudian dikirimkan secara kesleuruhan. Alasan dari penggunaan fixed-length header disini adalah karena payload yang dikirim dapat dipastikan tidak terlalu besar, sehingga tidak terlalu meningkatkan kompleksitas kode.

Dari sisi client, client mengirim payload command terlebih dahulu lalu dilayani oleh server. Dilanjutkan dengan blocking `recv()` sampai data diterima seutuhnya. Karena tidak terdapat informasi yang jelas terkait implementasi list, diasumsikan perintah `/list` ini akan mendaftar seluruh file yang ada di direktori root yang sudah ditentukan saat inisialisasi objek `Server`.

```python
    def list(self):
        self.send_msg(b"/list")
        data = self.recv_msg()
        print(data.decode())
```

Pada fungsi `recv_msg()` diterapkan mekanisme unpacking fixed-length header.

```python
def recv_msg(self):
    header = self.socket.recv(4)

    if len(header) < 4:
        return None

    length = struct.unpack(">I", header)[0]

    buffer = b''
    while len(buffer) < length:
        buffer += self.socket.recv(length - len(buffer))

    return buffer
```

Perhatikan pengecekan apabila panjang header kurang dari 4. Pengecekan tersebut bertujuan agar client dapat menangani empty packet yang dikirimkan oleh server ketika socket client ditutup.


#### Client Command: `/upload <filename>`

Tanpa memerhatikan edge cases umum, implementasi command `/upload` sangatlah sederhana karena upload sebatas file-file yang ada di relative directory. Berikut adalah logika untuk menangani upload pada server.

```python
def handle_upload(self, sock, filename):
    filepath = f"{self.root_dir}/{filename}"
    recv_file(sock, filepath)
```

Pengiriman file besar dari client ke server cukup berisiko tinggi. Oleh karena itu, pada `recv_file()` diimplementasikan chunked blocks header sehingga file besar tidak seutuhnya disimpan dalam memori terlebih dahulu sebelum pengiriman, yang mana dapat meningkatkan reliabilitas pengiriman.
```python
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
```

Tidak jauh berbeda dari sisi client, yakni cukup kebalikan dari sisi server. 
```python
def upload(self, path):
    self.send_msg(f"/upload {os.path.basename(path)}".encode())
    self.send_file(path)

def send_file(sock, path, chunk_size=4096):
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            sock.sendall(struct.pack(">I", len(chunk)) + chunk)
    sock.sendall(struct.pack(">I", 0))
```

#### Client Command: `/download <filename>`

Berikut adalah logika dari sisi server:
```python
def handle_download(self, sock, filename):
    filepath = f"{self.root_dir}/{filename}"
    send_file(sock, filepath)

def send_file(sock, path, chunk_size=4096):
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            sock.sendall(struct.pack(">I", len(chunk)) + chunk)
    sock.sendall(struct.pack(">I", 0))
```

Berikut adalah logika dari sisi client:
```python    
def download(self, filename):
    self.send_msg(f"/download {filename}".encode())
    filepath = f"{self.download_dir}/{filename}"

    print(f"Downloading {filename}...")

    self.recv_file(filepath)

    print(f"File {filename} downloaded.")
```

Dapat diperhatikan implementasi perintah `/download` pada server dan client di atas. Tidak jauh berbeda dengan `/upload`, yakni hanya sebatas melakukan download file-file yang berada di root directory server. Dengan alasan yang sama dengan implementasi `/upload`, digunakan pula chunked blocks header untuk framing payload. 

## Screenshot Hasil

