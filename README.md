# Nufatur Absensi — Sistem Absensi Karyawan & Manajemen Jobdesk

Aplikasi web **multi-user** (admin + karyawan) untuk absensi karyawan berfoto selfie
dengan **jam dari server**, plus checklist jobdesk harian, laporan, dan export Excel/PDF.

Dibangun dengan **Python standard library + SQLite** — tanpa `pip install`, tanpa Node.

```
Folder  : D:\MAGANG NIHHHHHH\absensi-server
Jalan   : klik dua kali jalankan.bat   (atau: python server.py)
Buka    : http://127.0.0.1:8080
Online  : https://nufaturabsensi-production.up.railway.app   (lihat bagian 7)
```

---

## 1. Fitur

### Admin (11 menu di sidebar)

| Menu | Isi |
|---|---|
| Dashboard | Total karyawan aktif, sudah absen, belum absen, terlambat, task selesai hari ini, tabel absensi harian, aktivitas terbaru |
| **Data Karyawan** | CRUD karyawan + **buat akun login** + reset password + filter/pencarian |
| Divisi & Kategori | CRUD divisi + daftar kategori jobdesk |
| Jobdesk Management | CRUD jobdesk (judul, kategori, deskripsi, berlaku untuk divisi tertentu/semua divisi) |
| Data Absensi | Filter tanggal/karyawan/divisi/status, jam masuk-pulang, durasi, telat, **thumbnail foto bukti** |
| Laporan Task Harian | Rekap penyelesaian jobdesk per karyawan per tanggal + export Excel/PDF |
| Laporan Kehadiran | Rekap kehadiran + kelengkapan bukti foto + export Excel/PDF + cetak |
| Monitoring Aktivitas | Jejak 200 aktivitas terakhir (login, absen, checklist, CRUD, export) |
| Pengaturan Jam Kerja | Jam masuk/pulang, toleransi telat, hari kerja, zona waktu, wajib foto, **nama instansi** |
| Pengaturan Akun | Ganti username, reset password, aktif/nonaktifkan akun, lihat login terakhir |
| Profil Saya | Ubah profil + ganti password sendiri |

### Karyawan (4 menu, navigasi bawah — dioptimalkan untuk HP)

| Menu | Isi |
|---|---|
| Absen | Kartu profil + jam berjalan, status hari ini, tombol **Absen Masuk** / **Absen Pulang** (wajib foto), ringkasan task, riwayat singkat |
| Task Harian | Checklist jobdesk sesuai divisinya, progress %, waktu selesai tercatat otomatis |
| Riwayat | Absensi 14 terakhir + riwayat task per tanggal |
| Profil | Foto profil, nama, ganti password, logout |

---

## 2. Cara menjalankan

**Cara cepat (Windows):** klik dua kali `jalankan.bat` — server hidup, browser terbuka sendiri.

**Manual:**

```bash
cd D:\MAGANG NIHHHHHH\absensi-server
python server.py                 # port 8080
python server.py --port 9000     # ganti port
python server.py --reset-db      # hapus database & buat ulang data contoh
```

Jendela server **harus tetap terbuka** selama aplikasi dipakai. Hentikan dengan `Ctrl + C`.

**Akses dari HP (satu jaringan Wi-Fi):** jalankan `LIHAT-ALAMAT-HP.bat`, lalu buka
`http://<IP-komputer>:8080` dari browser HP.

> Catatan kamera: browser hanya memberi akses kamera langsung (`getUserMedia`) di alamat
> **aman** — `http://127.0.0.1` atau `https://`. Kalau dibuka lewat IP LAN
> (`http://192.168.x.x`) kamera langsung diblokir browser; aplikasi otomatis menawarkan
> tombol **"Buka Kamera Perangkat"**. Foto tetap tersimpan dan absensi tetap sah.

**Akses dari internet:** klik dua kali `DEPLOY-INTERNET.bat` — menyalakan server + tunnel
Cloudflare, lalu mencetak alamat publik `https://...trycloudflare.com` dan menyimpannya ke
`URL-PUBLIK.txt`. Alamat berubah setiap tunnel dijalankan ulang; syarat hidup: jendela
**Server** + **Tunnel** harus tetap terbuka.

---

## 3. Login pertama & di mana password-nya

Saat pertama dijalankan, aplikasi membuat akun contoh dan menulisnya ke file:

```
AKUN-AWAL.txt      (1 akun admin + 6 akun karyawan contoh)
```

Password dibuat **acak** dan hanya ada di file itu.

> Kalau password sudah pernah diganti, isi `AKUN-AWAL.txt` **tidak berlaku lagi** —
> yang berlaku adalah password yang terakhir diatur. Admin bisa mereset password
> karyawan kapan saja (lihat 4.2); karyawan bisa ganti sendiri di **Profil**.

---

## 4. Panduan Admin

### 4.1 Bikin akun karyawan — bisa lewat admin, ya

Dua cara, dua-duanya dari menu **Data Karyawan**:

**A. Sekalian saat menambah karyawan baru**
1. Menu **Data Karyawan** → tombol **Tambah Karyawan**.
2. Isi nama, NIK, jabatan, divisi, kontak, tanggal masuk, status.
3. Biarkan centang **"Buatkan akun login untuk karyawan ini"** (default menyala).
4. Simpan → muncul dialog berisi **username** + **password awal**.
   **Catat sekarang — password ini tidak ditampilkan lagi.**
5. Karyawan login di halaman depan, lalu sebaiknya ganti password sendiri.

**B. Karyawan sudah ada, akunnya belum dibuat**
1. Menu **Data Karyawan** → cari baris karyawannya.
2. Klik tombol **Buat Akun** → dicatat username + password awalnya.

Catatan:
- Username dibuat otomatis dari nama (contoh: `budi`). Bisa diubah di
  **Pengaturan Akun → Ubah**.
- **NIK harus unik** antar karyawan.
- Status **karyawan** (`aktif`/`nonaktif`) beda dengan status **akun**
  (aktif/nonaktif). Karyawan nonaktif tidak muncul di daftar absensi harian.

### 4.2 Reset password & kelola akun
- **Pengaturan Akun**: ganti username, **Password** (reset), **Nonaktifkan/Aktifkan**,
  lihat login terakhir.
- **Data Karyawan** juga punya tombol **Password** per baris untuk reset cepat.
- Password hasil reset selalu ditampilkan **sekali** — langsung catat.

### 4.3 Atur jam kerja
Menu **Pengaturan Jam Kerja**: jam masuk, jam pulang, toleransi telat (menit), hari kerja,
zona waktu, wajib/tidak wajib foto, dan **nama instansi** (ini yang tampil di sidebar,
header karyawan, dan judul halaman).

### 4.4 Jobdesk & divisi
- **Divisi & Kategori**: bikin divisi (mis. Keuangan, Operasional).
- **Jobdesk Management**: bikin daftar pekerjaan; pilih berlaku untuk divisi tertentu
  atau **semua divisi**. Jobdesk nonaktif tidak muncul di checklist harian.

### 4.5 Lihat absensi & laporan
- **Data Absensi**: filter per hari / rentang tanggal / karyawan / divisi / status.
  Foto bukti berbentuk thumbnail — klik untuk memperbesar.
- **Laporan Kehadiran / Laporan Task Harian**: rekap + tombol **Excel**, **PDF**, **Cetak**.
- **Monitoring Aktivitas**: siapa melakukan apa (login, absen, checklist, CRUD, export).

---

## 5. Panduan Karyawan

1. Login pakai username + password dari admin.
2. Menu **Absen** → tekan **Absen Masuk** → kamera terbuka → foto selfie → simpan.
3. Kerjakan jobdesk hari ini di menu **Task Harian** — centang tiap pekerjaan yang selesai
   (waktu selesai tercatat otomatis).
4. Selesai kerja → menu **Absen** → **Absen Pulang** (juga pakai foto).
5. **Riwayat** untuk melihat absensi & task hari-hari sebelumnya.

Aturan yang dijaga server:

- **Jam absensi selalu dari server** — HP karyawan tidak bisa mengakali jam.
- **Satu kali sehari:** absen masuk 2× ditolak; absen pulang tanpa absen masuk ditolak.
- **Foto wajib.** Foto ditolak = absensi tidak tersimpan sama sekali.
- **Terlambat** dihitung otomatis dari jam masuk kerja + toleransi.
- Karyawan **hanya bisa melihat datanya sendiri**.

---

## 6. Tampilan di HP

- **Halaman karyawan** dirancang mobile-first (navigasi bawah, tombol besar).
- **Halaman admin** responsif: di layar ≤ 900px sidebar otomatis jadi **laci (drawer)**.
  - Tombol **☰** di kiri atas untuk membuka menu.
  - Ketuk area gelap di luar menu (atau pilih menu) untuk menutup.
  - Tabel data bisa **digeser ke samping** (tidak terpotong).
  - Di layar kecil (≤ 560px) teks nama/role kanan atas disembunyikan — tinggal avatar + keluar.

---

## 7. Deploy ke internet (Railway)

Sudah pernah dipasang di Railway (URL contoh di atas). Ringkasnya:

1. Repo GitHub: `NaufalFarras248/nufaturabsensi`.
2. Build pakai **Dockerfile** (`python:3.12-slim`), **bukan Nixpacks** — Nixpacks salah
   mendeteksi project ini sebagai situs statis (karena ada `static/index.html`) sehingga
   menghasilkan image nginx tanpa `python` (gejala: error 502).
3. Start command: `python server.py --host 0.0.0.0 --port $PORT` (sudah ada di `railway.json`).
4. **WAJIB pasang Volume** di mount `/data` + env `ABSENSI_DATA_DIR=/data` dan
   `ABSENSI_FOTO_DIR=/data/foto`. Tanpa volume, database + foto hilang setiap redeploy.

---

## 8. Data & backup

```
data/app.db            <- database SQLite (semua data)
storage/foto/YYYY-MM/  <- foto absensi (JPEG/PNG)
storage/foto/profil/   <- foto profil
```

**Backup:** salin `data/app.db` **dan** folder `storage/foto/` (keduanya berdampingan).
Atau pakai export Excel/PDF dari menu laporan untuk arsip periodik.

**Mulai dari nol:** `python server.py --reset-db` (database dihapus & dibuat ulang dengan
data contoh).

---

## 9. Bila ada masalah

| Masalah | Solusi |
|---|---|
| `python` tidak dikenali | Pakai `py server.py`, atau pasang Python dari python.org (centang "Add to PATH") |
| Port 8080 dipakai program lain | `python server.py --port 9000` |
| Kamera tidak muncul di HP | Buka lewat `https://` (hasil tunnel) atau pakai tombol "Buka Kamera Perangkat" |
| Login gagal terus | Cek password terakhir yang diatur; admin reset lewat **Pengaturan Akun → Password** |
| Karyawan bilang "jam salah" | Jam diambil dari server — betulkan jam komputer server |
| Data hilang setelah deploy ulang | Volume belum dipasang (lihat bagian 7) |
| Foto lama ingin diarsipkan | Salin `storage/foto/` + `data/app.db` |

---

## 10. Keamanan (ringkas)

- Password: **PBKDF2-HMAC-SHA256, 200.000 iterasi**, salt acak per akun.
- Sesi: token acak 32 byte, cookie **HttpOnly + SameSite=Strict**, umur 12 jam.
- Setiap request tulis wajib header **`X-CSRF`** (token per sesi) — tanpa itu 403.
- Otorisasi diperiksa **di server** tiap request; karyawan hanya bisa data miliknya.
- Foto disajikan lewat `/api/photo/<id>` dengan pemeriksaan kepemilikan.
- Rate limit login: 8 kali gagal dari satu IP → diblokir 5 menit.
- Halaman `/admin/*` hanya untuk admin; karyawan yang mengetik URL admin dialihkan
  (dan tercatat di Monitoring Aktivitas).

---

## 11. Struktur file & catatan teknis

```
absensi-server/
  server.py            HTTP server, routing, autentikasi, otorisasi, seluruh API
  db.py                skema SQLite, seed data contoh, query, aturan bisnis
  report.py            penulis .xlsx dan .pdf (stdlib, tanpa dependensi)
  test_api.py          uji end-to-end API
  rotate_password.py   ganti semua password sekaligus (opsional)
  jalankan.bat         launcher lokal (server + browser)
  DEPLOY-INTERNET.bat  launcher tunnel Cloudflare
  LIHAT-ALAMAT-HP.bat  tampilkan alamat IP LAN
  Dockerfile           build image (Railway)
  railway.json         konfigurasi deploy Railway
  static/
    index.html         halaman login
    admin.html         kerangka panel admin      + admin.js
    karyawan.html      kerangka panel karyawan   + karyawan.js
    ui.js              modul bersama: API, modal, toast, kamera selfie, format
    app.css            desain sistem (termasuk responsif HP)
  data/app.db          database
  storage/foto/        foto bukti absensi
  AKUN-AWAL.txt        akun awal (dibuat otomatis saat pertama jalan)
```

**Brand & warna** (semua CSS variable di `static/app.css`, blok `:root`):

| Warna | Hex | Dipakai di |
|---|---|---|
| Biru (wordmark) | `#1D7AB7` | tombol, link, tabel, nav aktif |
| Hijau (ujung pita) | `#0AD470` | absen masuk, badge hadir, checklist |
| Tosca (tengah pita) | `#17BAD9` | ikon daftar fitur, gradasi aksen |
| Marine black | `#03121A` | sidebar admin, hero karyawan & login |

Gradasi brand: `linear-gradient(120deg,#0AD470,#17BAD9,#1D7AB7)` (`--brand-grad`).
Nama instansi yang tampil di UI diambil dari **Pengaturan Jam Kerja** dan disimpan di
tabel `work_settings.nama_instansi`.

**Database (SQLite)** — tabel: `divisions`, `employees`, `users`, `attendance`,
`attendance_photos`, `jobdesks`, `daily_tasks`, `work_settings`, `sessions`, `activity_log`.
Foreign key aktif, `ON DELETE CASCADE` untuk data anak, `journal_mode = WAL`.

**API singkat** (semua di bawah `/api/`): `login`, `logout`, `me`, `employees[/<id>]`,
`employees/<id>/akun`, `divisions`, `jobdesks`, `attendance`, `attendance/masuk`,
`attendance/pulang`, `tasks/toggle`, `dashboard/admin`, `dashboard/karyawan`,
`reports/attendance`, `reports/tasks`, `export/xlsx`, `export/pdf`, `settings`, `log`,
`profil`.

**Uji otomatis:** jalankan server dulu, lalu `python test_api.py` (uji login, CSRF,
pembatasan role, foto wajib/palsu ditolak, jam server, absen ganda, checklist, laporan,
export Excel/PDF, dan pemisahan halaman admin/karyawan).
