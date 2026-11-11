# Nufatur Absensi — Sistem Absensi Karyawan & Task Management

Aplikasi web **multi-user** (admin + karyawan) dengan login, hak akses berbasis role,
absensi berfoto selfie dengan **jam dari server**, dan checklist jobdesk harian.
Dibangun dengan **Python standard library + SQLite** — tanpa pip, tanpa node, tanpa internet.

```
Folder : C:\Users\ASUS\Downloads\absensi-server
Jalan  : klik dua kali  jalankan.bat   (atau: python server.py)
Buka   : http://127.0.0.1:8080
```

**Brand & tampilan** — palet diambil langsung dari logo, file di `static/`:

| Aset | Isi |
|---|---|
| `static/logo.png` | lockup penuh (simbol + wordmark), halaman login |
| `static/logo-mark.png` | simbol saja, header sidebar admin |
| `static/logo-word.png` | wordmark saja, header halaman karyawan |
| `static/favicon.png` | favicon ketiga halaman |

| Warna | Hex | Dipakai di |
|---|---|---|
| Biru (wordmark) | `#1D7AB7` | tombol, link, tabel, nav aktif |
| Hijau (ujung pita) | `#0AD470` | absen masuk, badge hadir, checklist |
| Tosca (tengah pita) | `#17BAD9` | ikon daftar fitur, gradasi aksen |
| Marine black (latar logo) | `#03121A` | sidebar admin, hero karyawan & login |

Semua warna didefinisikan sebagai CSS variable di `static/app.css` blok `:root`.
Gradasi brand: `linear-gradient(120deg,#0AD470,#17BAD9,#1D7AB7)` (`--brand-grad`).

---

## 1. Cara menjalankan

**Cara cepat (Windows):** klik dua kali `jalankan.bat` — server hidup, browser terbuka sendiri.

**Cara manual:**
```bash
cd C:\Users\ASUS\Downloads\absensi-server
python server.py                # port 8080
python server.py --port 9000    # ganti port
python server.py --reset-db     # hapus database & buat ulang data contoh
```
Jendela server **harus tetap terbuka** selama aplikasi dipakai. Hentikan dengan `Ctrl + C`.

**Akses dari HP (satu jaringan Wi-Fi):** server mencetak alamat LAN saat dijalankan,
misal `http://192.168.1.10:8080`. Buka alamat itu dari browser HP.

> Catatan kamera: browser hanya mengizinkan akses kamera langsung (`getUserMedia`) pada
> alamat **aman** — `http://127.0.0.1` atau `https://`. Kalau diakses lewat IP LAN
> (http://192.168.x.x) kamera langsung diblokir browser; aplikasi otomatis menawarkan
> tombol **"Buka Kamera Perangkat"** yang memakai aplikasi kamera bawaan HP. Foto tetap
> tersimpan dan absensi tetap sah.

**Deploy ke internet (bisa dibuka dari mana saja, bukan cuma Wi-Fi):**

```
Klik dua kali : DEPLOY-INTERNET.bat
```

Skrip itu menyalakan `server.py` bila belum jalan, membuka tunnel Cloudflare,
lalu mencetak **alamat publik https** dan menyimpannya ke `URL-PUBLIK.txt`.

| Perlu tahu | Keterangan |
|---|---|
| Alamat publik | acak, contoh `https://xxx-yyy-zzz.trycloudflare.com` |
| Ganti tiap | tunnel dijalankan ulang — selalu baca `URL-PUBLIK.txt` |
| Syarat hidup | jendela **Server Absensi Karyawan** + **Tunnel Absensi** harus terbuka |
| Bonus | https = alamat aman, jadi kamera HP langsung jalan di dalam halaman |
| Mati saat | komputer dimatikan / sleep, atau salah satu jendela ditutup |
| Komponen | `tools\cloudflared.exe` (Cloudflare Tunnel, tanpa akun) |

> **Sebelum alamat publik dibagikan:** password default **wajib** diganti. Jalankan
> `python rotate_password.py` — semua password lama mati, semua sesi diputus, dan
> password baru ditulis ke `AKUN-BARU.txt` (tidak pernah muncul di layar). Untuk
> mempersempit ke satu akun saja, ganti lewat *Profil Saya → Ganti Password*.
>
> Semua endpoint `/api/*` menolak akses tanpa login (401). Batas percobaan login:
> 8 kali gagal dari satu IP → diblokir 5 menit.

Untuk alamat yang **tetap** (tidak berubah tiap restart) dibutuhkan tunnel bernama
dengan akun Cloudflare + domain sendiri; itu tidak bisa dilakukan tanpa akun.

---

## 2. Akun awal

Saat pertama dijalankan, aplikasi membuat akun contoh dan menulisnya ke file:

```
C:\Users\ASUS\Downloads\absensi-server\AKUN-AWAL.txt
```

Isinya: 1 akun **admin** + 6 akun **karyawan** (username `andi`, `budi`, `citra`, `dedi`,
`eka`, `fajar`). Password dibuat acak dan **hanya ada di file itu**.

> **Status sekarang: password sudah dirotasi.** Semua password di `AKUN-AWAL.txt` **mati**.
> Password yang berlaku ada di `AKUN-BARU.txt` (8 akun), dibuat oleh `python rotate_password.py`.
> Jalankan skrip itu lagi kapan saja untuk mengganti semua password sekaligus.

Ganti password satu akun lewat menu *Profil Saya → Ganti Password*, atau sebagai admin
lewat *Pengaturan Akun*.

Admin dapat membuat akun karyawan baru kapan saja di menu **Data Karyawan → Tambah Karyawan**
(centang "Buatkan akun login"), dan password baru selalu ditampilkan sekali untuk dicatat.

---

## 3. Sistem 2 role (RBAC) & struktur URL

Aplikasi hanya punya **dua role**: `admin` dan `karyawan`. Role tersimpan di kolom
`users.role` (CHECK constraint di database) dan ditentukan **oleh server** pada setiap request
— bukan dari tampilan.

| URL | Siapa yang boleh | Keterangan |
|---|---|---|
| `/` | semua | belum login -> halaman login; sudah login -> dialihkan ke dashboard role-nya |
| `/admin/dashboard` | admin | dashboard admin |
| `/admin/<menu>` | admin | menu: dashboard, karyawan, divisi, jobdesk, absensi, lap-task, lap-hadir, monitor, set-jam, akun, profil |
| `/employee/dashboard` | karyawan | dashboard karyawan (absen, jam berjalan, task hari ini) |
| `/employee/<menu>` | karyawan | menu: dashboard, task, riwayat, profil |

Aturan pengalihan (semuanya diuji otomatis):

- belum login membuka `/admin/*` atau `/employee/*` -> dialihkan ke `/?masuk=1`
- **karyawan mengetik URL admin** -> dialihkan ke `/employee/dashboard`; HTML panel admin
  tidak pernah dikirim ke browser karyawan
- admin membuka URL karyawan -> dialihkan ke `/admin/dashboard`
- menu tidak dikenal -> dialihkan ke dashboard role tersebut
- jalur lama `/admin.html` dan `/karyawan.html` mengikuti aturan role yang sama

Sidebar admin dan navigasi bawah karyawan **berbeda**, dan URL ikut berubah saat menu diklik
(`/admin/absensi`, `/employee/task`, ...) sehingga tombol back/forward browser bekerja.

### Matriks hak akses

| Kemampuan | Admin | Karyawan |
|---|---|---|
| Dashboard | seluruh karyawan | hanya dirinya |
| Tambah / edit / hapus / nonaktifkan karyawan | ya | tidak |
| Atur username, email, dan password karyawan | ya | tidak |
| Jobdesk: tambah / edit / hapus | ya | hanya melihat daftar jobdesk divisinya |
| Lihat absensi + foto bukti karyawan lain | ya | tidak, hanya miliknya sendiri |
| Lihat & koreksi checklist pekerjaan karyawan | ya (semua karyawan, tanggal bebas) | hanya miliknya, hanya hari ini |
| Laporan + export Excel/PDF | ya | tidak |
| Pengaturan jam kerja & pengaturan akun | ya | tidak |
| Absen masuk / pulang dengan foto | - | ya |
| Ubah jam absensi manual | tidak bisa | tidak bisa |
| Ubah role akun sendiri | lewat menu akun | **tidak bisa** (diabaikan server) |

## 4. Fitur per role

### Admin (sidebar, 11 menu)

| Menu | Isi |
|---|---|
| Dashboard | Total karyawan aktif, sudah absen masuk, belum absen, terlambat, sudah absen pulang, total task selesai hari ini, tabel absensi harian, aktivitas terbaru |
| Data Karyawan | CRUD karyawan (nama, NIK, jabatan, divisi, kontak, tgl masuk, status), buat akun login, reset password, filter divisi/status + pencarian |
| Divisi & Kategori | CRUD divisi + daftar kategori jobdesk yang dipakai |
| Jobdesk Management | CRUD jobdesk: judul, kategori, deskripsi, berlaku untuk divisi tertentu atau semua divisi, aktif/nonaktif |
| Data Absensi | Filter per hari / rentang tanggal / karyawan / divisi / status, jam masuk-pulang, durasi, menit terlambat, status, **thumbnail foto bukti**, detail lengkap |
| Laporan Task Harian | Rekap penyelesaian jobdesk per karyawan per tanggal + daftar pekerjaan yang diselesaikan + export Excel/PDF |
| Laporan Kehadiran | Rekap jam masuk/pulang, durasi, keterlambatan, bukti foto lengkap atau tidak, persen task + export Excel/PDF + cetak |
| Monitoring Aktivitas | Jejak 200 aktivitas terakhir (login, absen, checklist, CRUD, export) |
| Pengaturan Jam Kerja | Jam masuk, jam pulang, toleransi keterlambatan, hari kerja, zona waktu, wajib/tidak wajib foto selfie, nama instansi |
| Pengaturan Akun | Ganti username, reset password, aktif/nonaktifkan akun, lihat login terakhir |
| Profil Saya | Ubah profil + ganti password sendiri |

### Karyawan (navigasi bawah, 4 menu)

| Menu | Isi |
|---|---|
| Absen | Kartu profil + jam berjalan, status hari ini, tombol **Absen Masuk** dan **Absen Pulang** (wajib foto kamera), jam masuk/pulang/durasi, ringkasan task hari ini, riwayat singkat |
| Task Harian | Daftar jobdesk sesuai divisinya, checklist per hari, progress persen, waktu selesai tercatat otomatis |
| Riwayat | Riwayat absensi (14 terakhir) dan riwayat task per tanggal dengan filter rentang |
| Profil | Foto profil (kamera/galeri), nama, ganti password, logout |

---

## 5. Aturan bisnis yang dijalankan server

- **Jam absensi = waktu server.** Klien tidak pernah mengirim jam; kalau mencoba mengirim,
  diabaikan. Semua jam disimpan dalam `attendance.checkin_at` / `checkout_at` (WIB lokal server).
- **Foto wajib.** Foto divalidasi **sebelum** data absensi ditulis: tipe (JPEG/PNG/WEBP),
  magic bytes, ukuran 2 KB–6 MB. Foto ditolak = absensi tidak tersimpan sama sekali.
- **Satu kali per hari.** Absen masuk dua kali → ditolak. Absen pulang dua kali → ditolak.
  Absen pulang tanpa absen masuk → ditolak.
- **Terlambat** dihitung otomatis: jam masuk server > jam masuk kerja + toleransi (default
  10 menit). Contoh: masuk 08:15 dengan toleransi 10 menit → **Terlambat 5 menit**.
- **Status tampilan:** Hadir · Terlambat · Belum Absen Pulang · Tidak Hadir.
- **Durasi kerja** = jam pulang − jam masuk (dihitung dari epoch, aman untuk shift malam).
- **Checklist task** hanya boleh diisi **hari ini** oleh pemiliknya, dan hanya jobdesk yang
  berlaku untuk divisinya. Admin boleh mengoreksi tanggal lain bila perlu.
- **Karyawan hanya melihat datanya sendiri.** Semua pembatasan diperiksa di server
  (bukan hanya disembunyikan di tampilan).

---

## 6. Database (SQLite)

```
data/app.db          <- database
storage/foto/YYYY-MM/ <- file foto absensi (JPEG/PNG)
storage/foto/profil/ <- foto profil
```

| Tabel | Isi | Relasi |
|---|---|---|
| `divisions` | divisi kerja | — |
| `employees` | data karyawan | `division_id → divisions.id` |
| `users` | akun login (admin & karyawan) | `employee_id → employees.id` |
| `attendance` | absensi harian | `employee_id → employees.id`, unik per (karyawan, tanggal) |
| `attendance_photos` | foto bukti absensi | `attendance_id → attendance.id` (jenis: checkin/checkout) |
| `jobdesks` | daftar pekerjaan | `division_id → divisions.id` (NULL = semua divisi) |
| `daily_tasks` | checklist harian | `employee_id`, `jobdesk_id` (unik per karyawan/jobdesk/tanggal) |
| `work_settings` | jam kerja, toleransi, hari kerja | 1 baris (id = 1) |
| `sessions` | sesi login (token + CSRF) | `user_id → users.id` |
| `activity_log` | jejak aktivitas | `user_id → users.id` |

Foreign key aktif, `ON DELETE CASCADE` untuk data anak, `journal_mode = WAL`.

**Backup:** salin `data/app.db` **dan** folder `storage/foto/` (keduanya berdampingan).
Atau lewat menu *Data Absensi/Laporan → Excel* untuk arsip laporan.

---

## 7. Keamanan

- Password: **PBKDF2-HMAC-SHA256, 200.000 iterasi**, salt acak per akun.
- Sesi: token acak 32 byte di tabel `sessions`, cookie **HttpOnly + SameSite=Strict**, umur 12 jam.
- **CSRF:** setiap request tulis (POST/PUT/DELETE) wajib menyertakan header `X-CSRF` yang cocok
  dengan token sesi. Tanpa itu → 403.
- **Otorisasi per endpoint** di server: `admin` vs `karyawan`; karyawan hanya bisa data sendiri.
- Foto absensi disajikan lewat `/api/photo/<id>` yang memeriksa kepemilikan (admin semua,
  karyawan hanya fotonya sendiri).
- Rate limit login: 8 kali gagal dari satu IP → ditolak 5 menit.
- Semua input divalidasi di server (panjang, format tanggal, format jam, angka, tipe).
- **Pemisahan halaman per role di server**: `/admin/*` hanya untuk admin, `/employee/*` hanya
  untuk karyawan; karyawan yang mengetik URL admin dicatat di Monitoring Aktivitas dan
  langsung dialihkan tanpa pernah menerima halaman admin.

---

## 8. API singkat

```
GET  /                     -> login / alihkan ke dashboard sesuai role
GET  /admin/<menu>         -> panel admin (khusus admin)
GET  /employee/<menu>      -> panel karyawan (khusus karyawan)

POST /api/login                  {username,password}         -> {user, csrf}, set cookie
POST /api/logout
GET  /api/me                     -> user + csrf + pengaturan + jam server

GET/POST/PUT/DELETE  /api/employees[/<id>]        (admin; karyawan hanya baca dirinya)
POST /api/employees/<id>/akun                     (admin) -> username + password awal
GET/POST/PUT/DELETE  /api/divisions, /api/jobdesks
GET  /api/attendance?from&to&employee_id&division_id&status&q
POST /api/attendance/masuk       {foto: dataURL}   -> jam dari server
POST /api/attendance/pulang      {foto: dataURL}
GET  /api/attendance/hari-ini
GET  /api/photo/<id>                               -> file foto (dengan otorisasi)
GET  /api/tasks?tanggal&employee_id
POST /api/tasks/toggle           {jobdesk_id, tanggal, selesai}
GET  /api/tasks/riwayat?from&to
GET  /api/dashboard/admin?tanggal | /api/dashboard/karyawan
GET  /api/reports/attendance | /api/reports/tasks  (filter from,to,division_id,employee_id,q)
GET  /api/export/xlsx?jenis=kehadiran|task&...     -> .xlsx asli
GET  /api/export/pdf?jenis=kehadiran|task&...      -> .pdf asli
GET/PUT /api/settings  (PUT khusus admin)
GET  /api/log?limit=200 (admin)   GET/PUT /api/profil   POST /api/profil/password
```

---

## 9. Pengujian otomatis

```bash
python server.py                        # terminal 1 (biarkan berjalan)
python test_api.py                      # terminal 2
```

`test_api.py` menguji 74 hal: login salah/benar, CSRF, pembatasan role, foto wajib,
foto palsu ditolak, foto gagal tidak menyisakan data, jam memakai waktu server,
absen dua kali, absen pulang, checklist task + waktu selesai, jobdesk divisi lain
ditolak, dashboard, laporan, export Excel/PDF (dicek magic bytes), pengaturan jam,
ganti password, **pemisahan halaman admin/karyawan lewat URL** (karyawan mengetik
`/admin/dashboard` ditolak, role tidak bisa dinaikkan sendiri), logout, dan
bersih-bersih data uji.

---

## 10. Bila ada masalah

| Masalah | Solusi |
|---|---|
| `python` tidak dikenali | Pakai `py server.py`, atau pasang Python dari python.org (centang "Add to PATH") |
| Port 8080 dipakai program lain | `python server.py --port 9000` |
| Kamera tidak muncul di HP | Buka lewat `http://127.0.0.1` (di komputer) atau pakai tombol "Buka Kamera Perangkat" |
| Login gagal terus | Lihat `AKUN-AWAL.txt`; bila perlu admin reset password dari *Pengaturan Akun* |
| Data ingin dimulai dari nol | `python server.py --reset-db` (database & data contoh dibuat ulang) |
| Foto lama ingin diarsipkan | Salin `storage/foto/` + `data/app.db` |

---

## 11. Struktur file

```
absensi-server/
  server.py         HTTP server, routing, autentikasi, otorisasi, seluruh API
  db.py             skema SQLite, seed data contoh, query, aturan bisnis
  report.py         penulis .xlsx dan .pdf (stdlib, tanpa dependensi)
  test_api.py       uji end-to-end API (55 pemeriksaan)
  jalankan.bat      launcher: jalankan server + buka browser
  static/
    index.html      halaman login
    admin.html      kerangka panel admin      + admin.js
    karyawan.html   kerangka panel karyawan   + karyawan.js
    ui.js           modul bersama: API, modal, toast, kamera selfie, format
    app.css         desain sistem (navy / abu / biru)
  data/app.db       database
  storage/foto/     penyimpanan foto bukti absensi
  AKUN-AWAL.txt     akun awal (dibuat otomatis saat pertama jalan)
```
