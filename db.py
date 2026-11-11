"""
db.py — Skema, koneksi, seed, dan seluruh query database.
Database: SQLite (stdlib, tanpa dependensi eksternal).
Tabel: users, employees, divisions, attendance, attendance_photos,
       jobdesks, daily_tasks, work_settings, sessions, activity_log.
"""
import os
import sqlite3
import hashlib
import secrets
import datetime as dt

BASE = os.path.dirname(os.path.abspath(__file__))
# Bisa dioverride lewat env (dipakai saat deploy: volume persisten).
DATA_DIR = os.environ.get('ABSENSI_DATA_DIR') or os.path.join(BASE, 'data')
FOTO_DIR = os.environ.get('ABSENSI_FOTO_DIR') or os.path.join(BASE, 'storage', 'foto')
DB_PATH = os.path.join(DATA_DIR, 'app.db')

PBKDF2_ROUNDS = 200_000

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS divisions (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  nama          TEXT NOT NULL UNIQUE,
  keterangan    TEXT NOT NULL DEFAULT '',
  created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS employees (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  nama          TEXT NOT NULL,
  nik           TEXT UNIQUE,
  email         TEXT NOT NULL DEFAULT '',
  telepon       TEXT NOT NULL DEFAULT '',
  jabatan       TEXT NOT NULL DEFAULT '',
  division_id   INTEGER REFERENCES divisions(id) ON DELETE SET NULL,
  tgl_masuk     TEXT NOT NULL DEFAULT '',
  status        TEXT NOT NULL DEFAULT 'aktif' CHECK (status IN ('aktif','nonaktif')),
  foto_profil   TEXT NOT NULL DEFAULT '',
  created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  username      TEXT NOT NULL UNIQUE,
  email         TEXT NOT NULL DEFAULT '',
  password_hash TEXT NOT NULL,
  salt          TEXT NOT NULL,
  role          TEXT NOT NULL CHECK (role IN ('admin','karyawan')),
  employee_id   INTEGER REFERENCES employees(id) ON DELETE CASCADE,
  aktif         INTEGER NOT NULL DEFAULT 1,
  created_at    TEXT NOT NULL,
  last_login    TEXT
);

CREATE TABLE IF NOT EXISTS attendance (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  employee_id     INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  tanggal         TEXT NOT NULL,
  checkin_at      TEXT,
  checkin_epoch   INTEGER,
  checkout_at     TEXT,
  checkout_epoch  INTEGER,
  status          TEXT NOT NULL DEFAULT 'Hadir',
  terlambat_menit INTEGER NOT NULL DEFAULT 0,
  durasi_menit    INTEGER,
  sumber          TEXT NOT NULL DEFAULT 'server',
  catatan         TEXT NOT NULL DEFAULT '',
  UNIQUE (employee_id, tanggal)
);

CREATE TABLE IF NOT EXISTS attendance_photos (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  attendance_id  INTEGER NOT NULL REFERENCES attendance(id) ON DELETE CASCADE,
  jenis          TEXT NOT NULL CHECK (jenis IN ('checkin','checkout')),
  file_path      TEXT NOT NULL,
  mime           TEXT NOT NULL DEFAULT 'image/jpeg',
  size           INTEGER NOT NULL DEFAULT 0,
  created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobdesks (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  judul         TEXT NOT NULL,
  kategori      TEXT NOT NULL DEFAULT '',
  division_id   INTEGER REFERENCES divisions(id) ON DELETE SET NULL,
  deskripsi     TEXT NOT NULL DEFAULT '',
  aktif         INTEGER NOT NULL DEFAULT 1,
  urutan        INTEGER NOT NULL DEFAULT 0,
  created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_tasks (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  employee_id    INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  jobdesk_id     INTEGER NOT NULL REFERENCES jobdesks(id) ON DELETE CASCADE,
  tanggal        TEXT NOT NULL,
  selesai        INTEGER NOT NULL DEFAULT 0,
  waktu_selesai  TEXT,
  UNIQUE (employee_id, jobdesk_id, tanggal)
);

CREATE TABLE IF NOT EXISTS work_settings (
  id              INTEGER PRIMARY KEY CHECK (id = 1),
  nama_instansi   TEXT NOT NULL DEFAULT 'Nufatur Absensi',
  jam_masuk       TEXT NOT NULL DEFAULT '08:00',
  jam_pulang      TEXT NOT NULL DEFAULT '17:00',
  toleransi_menit INTEGER NOT NULL DEFAULT 10,
  hari_kerja      TEXT NOT NULL DEFAULT '1,2,3,4,5',
  zona_waktu      TEXT NOT NULL DEFAULT 'WIB',
  wajib_foto      INTEGER NOT NULL DEFAULT 1,
  updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
  token         TEXT PRIMARY KEY,
  user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  csrf          TEXT NOT NULL,
  created_at    TEXT NOT NULL,
  expires_at    TEXT NOT NULL,
  ip            TEXT NOT NULL DEFAULT '',
  user_agent    TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS activity_log (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id     INTEGER,
  aksi        TEXT NOT NULL,
  detail      TEXT NOT NULL DEFAULT '',
  created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_att_tanggal   ON attendance (tanggal);
CREATE INDEX IF NOT EXISTS idx_att_employee  ON attendance (employee_id, tanggal);
CREATE INDEX IF NOT EXISTS idx_task_tanggal  ON daily_tasks (tanggal, employee_id);
CREATE INDEX IF NOT EXISTS idx_log_created   ON activity_log (created_at);
"""


# ------------------------------------------------------------------ waktu
def now():
    return dt.datetime.now()


def now_iso():
    return now().strftime('%Y-%m-%d %H:%M:%S')


def today():
    return now().strftime('%Y-%m-%d')


def epoch():
    return int(now().timestamp())


def menit_dari_jam(hhmm):
    """'08:15' -> 495. Tahan input kosong/None."""
    if not hhmm:
        return None
    try:
        h, m = str(hhmm).split(':')[:2]
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return None


def selisih_menit(t1, t2):
    """Selisih menit t2 - t1 untuk format 'HH:MM', tahan lewat tengah malam."""
    a, b = menit_dari_jam(t1), menit_dari_jam(t2)
    if a is None or b is None:
        return 0
    d = b - a
    if d < 0:
        d += 24 * 60
    return d


# ------------------------------------------------------------------ koneksi
def connect():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(FOTO_DIR, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys = ON')
    con.execute('PRAGMA journal_mode = WAL')
    return con


def q(sql, args=(), one=False):
    """SELECT -> list[dict] atau dict tunggal."""
    con = connect()
    try:
        cur = con.execute(sql, args)
        rows = [dict(r) for r in cur.fetchall()]
        return (rows[0] if rows else None) if one else rows
    finally:
        con.close()


def x(sql, args=()):
    """INSERT/UPDATE/DELETE -> lastrowid / rowcount."""
    con = connect()
    try:
        cur = con.execute(sql, args)
        con.commit()
        return cur.lastrowid if cur.lastrowid else cur.rowcount
    finally:
        con.close()


def log(user_id, aksi, detail=''):
    try:
        x('INSERT INTO activity_log (user_id, aksi, detail, created_at) VALUES (?,?,?,?)',
          (user_id, aksi, str(detail)[:500], now_iso()))
    except sqlite3.Error:
        pass


# ------------------------------------------------------------------ password
def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), PBKDF2_ROUNDS)
    return dk.hex(), salt


def verify_password(password, password_hash, salt):
    try:
        dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), PBKDF2_ROUNDS)
    except (ValueError, AttributeError):
        return False
    return secrets.compare_digest(dk.hex(), password_hash or '')


# ------------------------------------------------------------------ inisialisasi + seed
def _seed_rows(con):
    """Data contoh realistis supaya tidak ada layar kosong saat pertama dibuka."""
    t = now_iso()
    divisi = [
        ('Operasional', 'Gudang, produksi, dan lapangan'),
        ('Keuangan', 'Kas, pembukuan, dan administrasi'),
        ('Teknik', 'Mesin, perawatan, dan perbaikan'),
        ('Marketing', 'Penjualan, konten, dan layanan pelanggan'),
    ]
    for nama, ket in divisi:
        con.execute('INSERT INTO divisions (nama, keterangan, created_at) VALUES (?,?,?)', (nama, ket, t))

    div = {r['nama']: r['id'] for r in con.execute('SELECT id, nama FROM divisions').fetchall()}
    karyawan = [
        ('Andi Pratama', '2021001', 'Supervisor Operasional', 'Operasional', 'andi', '0812-1111-0001', '2021-03-01'),
        ('Budi Santoso', '2021002', 'Staff Gudang', 'Operasional', 'budi', '0812-1111-0002', '2021-07-15'),
        ('Citra Dewi', '2021003', 'Admin Keuangan', 'Keuangan', 'citra', '0812-1111-0003', '2022-01-10'),
        ('Dedi Kurniawan', '2021004', 'Teknisi Mesin', 'Teknik', 'dedi', '0812-1111-0004', '2022-06-01'),
        ('Eka Lestari', '2021005', 'Customer Service', 'Marketing', 'eka', '0812-1111-0005', '2023-02-20'),
        ('Fajar Nugroho', '2021006', 'Staff Konten', 'Marketing', 'fajar', '0812-1111-0006', '2024-08-05'),
    ]
    akun = []
    for nama, nik, jabatan, div_nama, username, telp, masuk in karyawan:
        con.execute(
            """INSERT INTO employees (nama, nik, email, telepon, jabatan, division_id, tgl_masuk, status, created_at)
               VALUES (?,?,?,?,?,?,?,'aktif',?)""",
            (nama, nik, username + '@contoh.co.id', telp, jabatan, div.get(div_nama), masuk, t))
        eid = con.execute('SELECT last_insert_rowid() AS i').fetchone()['i']
        pw = secrets.token_urlsafe(6)
        h, s = hash_password(pw)
        con.execute(
            """INSERT INTO users (username, email, password_hash, salt, role, employee_id, aktif, created_at)
               VALUES (?,?,?,?, 'karyawan', ?, 1, ?)""",
            (username, username + '@contoh.co.id', h, s, eid, t))
        akun.append((username, pw, nama))

    pw_admin = secrets.token_urlsafe(8)
    h, s = hash_password(pw_admin)
    con.execute(
        """INSERT INTO users (username, email, password_hash, salt, role, employee_id, aktif, created_at)
           VALUES ('admin','admin@contoh.co.id',?,?,'admin',NULL,1,?)""", (h, s, t))
    akun.insert(0, ('admin', pw_admin, 'Administrator'))

    jobdesk = [
        ('Membuat laporan harian', 'Administrasi', None, 'Rekap pekerjaan hari ini dan kirim ke atasan.', 1),
        ('Melakukan pengecekan stok barang', 'Gudang', 'Operasional', 'Cek fisik stok vs catatan sistem.', 2),
        ('Membalas pesan pelanggan', 'Layanan Pelanggan', 'Marketing', 'Respon chat/email pelanggan maks 5 menit.', 3),
        ('Mengelola database', 'IT', None, 'Backup, bersihkan data ganda, cek integritas.', 4),
        ('Membuat konten media sosial', 'Konten', 'Marketing', 'Satu konten per hari, upload terjadwal.', 5),
        ('Melakukan follow-up customer', 'Penjualan', 'Marketing', 'Hubungi calon pelanggan yang belum closing.', 6),
        ('Membersihkan area kerja', 'Kebersihan', None, 'Area kerja, meja, dan peralatan siap dipakai.', 7),
        ('Rekap kas dan rekonsiliasi bank', 'Keuangan', 'Keuangan', 'Cocokkan kas fisik dengan mutasi bank.', 8),
        ('Perawatan rutin mesin', 'Teknik', 'Teknik', 'Checklist mesin, pelumasan, cek suara abnormal.', 9),
        ('Update dokumentasi SOP', 'Administrasi', None, 'Revisi SOP bila ada perubahan proses.', 10),
    ]
    for judul, kat, div_nama, ket, urut in jobdesk:
        con.execute(
            """INSERT INTO jobdesks (judul, kategori, division_id, deskripsi, aktif, urutan, created_at)
               VALUES (?,?,?,?,1,?,?)""", (judul, kat, div.get(div_nama), ket, urut, t))

    con.execute(
        """INSERT INTO work_settings (id, nama_instansi, jam_masuk, jam_pulang, toleransi_menit,
           hari_kerja, zona_waktu, wajib_foto, updated_at)
           VALUES (1,'Nufatur Absensi','08:00','17:00',10,'1,2,3,4,5','WIB',1,?)""", (t,))

    # riwayat absensi 6 hari kerja terakhir (tanpa foto, sebagai contoh data lama)
    semua_emp = con.execute('SELECT id FROM employees ORDER BY id').fetchall()
    for d in range(1, 8):
        tgl = (now() - dt.timedelta(days=d))
        if tgl.weekday() >= 5:
            continue
        tanggal = tgl.strftime('%Y-%m-%d')
        for i, emp in enumerate(semua_emp):
            if (i + d) % 9 == 0:
                continue  # contoh hari tidak hadir
            telat = (i + d) % 4 == 0
            masuk = dt.datetime.combine(tgl.date(), dt.time(8, 0)) + dt.timedelta(minutes=(22 if telat else -3 + i))
            keluar = dt.datetime.combine(tgl.date(), dt.time(17, 0)) + dt.timedelta(minutes=(5 * i))
            con.execute(
                """INSERT INTO attendance (employee_id, tanggal, checkin_at, checkin_epoch, checkout_at,
                   checkout_epoch, status, terlambat_menit, durasi_menit, sumber)
                   VALUES (?,?,?,?,?,?,?,?,?,'seed')""",
                (emp['id'], tanggal, masuk.strftime('%Y-%m-%d %H:%M:%S'), int(masuk.timestamp()),
                 keluar.strftime('%Y-%m-%d %H:%M:%S'), int(keluar.timestamp()),
                 'Terlambat' if telat else 'Hadir', 22 if telat else 0,
                 int((keluar - masuk).total_seconds() // 60)))
    return akun


def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(FOTO_DIR, exist_ok=True)
    con = connect()
    try:
        con.executescript(SCHEMA)
        con.commit()
        ada = con.execute('SELECT COUNT(*) AS c FROM users').fetchone()['c']
        if not ada:
            akun = _seed_rows(con)
            con.commit()
            _tulis_akun_awal(akun)
    finally:
        con.close()


def _tulis_akun_awal(akun):
    """Simpan password awal ke file lokal, BUKAN ke layar/log."""
    path = os.path.join(BASE, 'AKUN-AWAL.txt')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('AKUN AWAL NUFATUR ABSENSI\n')
        f.write('Dibuat: %s\n' % now_iso())
        f.write('Segera ganti password admin lewat menu Profil.\n')
        f.write('=' * 58 + '\n')
        f.write('%-14s %-22s %s\n' % ('USERNAME', 'PASSWORD', 'NAMA'))
        f.write('-' * 58 + '\n')
        for username, pw, nama in akun:
            f.write('%-14s %-22s %s\n' % (username, pw, nama))
        f.write('=' * 58 + '\n')
    return path


# ------------------------------------------------------------------ setting & helper bisnis
def settings():
    s = q('SELECT * FROM work_settings WHERE id = 1', one=True)
    if not s:
        x("""INSERT INTO work_settings (id, updated_at) VALUES (1, ?)""", (now_iso(),))
        s = q('SELECT * FROM work_settings WHERE id = 1', one=True)
    return s


def status_absensi(row, set_):
    """Status tampilan: Hadir | Terlambat | Belum Absen Pulang | Tidak Hadir."""
    if not row:
        return 'Tidak Hadir'
    if not row.get('checkout_at'):
        return 'Belum Absen Pulang'
    return row.get('status') or 'Hadir'


def jobdesk_untuk(employee_id):
    """Jobdesk aktif yang berlaku untuk karyawan: divisinya sendiri atau untuk semua."""
    emp = q('SELECT division_id FROM employees WHERE id = ?', (employee_id,), one=True)
    div = emp['division_id'] if emp else None
    return q("""SELECT j.*, d.nama AS divisi FROM jobdesks j
                LEFT JOIN divisions d ON d.id = j.division_id
                WHERE j.aktif = 1 AND (j.division_id IS NULL OR j.division_id = ?)
                ORDER BY j.urutan, j.id""", (div,))


def hitung_status_masuk(menit_masuk, set_):
    """Return (status, terlambat_menit) berdasarkan jam masuk server vs setting."""
    batas = menit_dari_jam(set_['jam_masuk'])
    if batas is None or menit_masuk is None:
        return 'Hadir', 0
    telat = menit_masuk - batas
    if telat > int(set_['toleransi_menit']):
        return 'Terlambat', telat
    return 'Hadir', 0
