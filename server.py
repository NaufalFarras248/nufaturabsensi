"""
server.py — Nufatur Absensi (Aplikasi Absensi Karyawan & Task Management, server lokal).
Python standard library saja: http.server + sqlite3 + hashlib. Tanpa pip, tanpa node.

Jalankan:  python server.py            (default http://127.0.0.1:8080)
           python server.py --port 9000

Keamanan:
  * password  : PBKDF2-HMAC-SHA256, 200k iterasi, salt per akun
  * sesi      : token acak 32 byte di tabel sessions, cookie HttpOnly + SameSite=Strict
  * CSRF      : token per sesi wajib di header X-CSRF untuk semua request tulis
  * otorisasi : dicek di server tiap request; karyawan hanya bisa data miliknya
  * waktu     : diambil dari server (datetime.now()), karyawan tidak bisa mengirim jam
  * foto      : divalidasi tipe + magic bytes + ukuran sebelum disimpan ke storage/foto
"""
import argparse
import base64
import binascii
import datetime as dt
import json
import mimetypes
import os
import re
import secrets
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

import db
import report

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE, 'static')
FOTO_DIR = db.FOTO_DIR
MAX_BODY = 8 * 1024 * 1024          # 8 MB (foto selfie base64)
MAX_FOTO = 6 * 1024 * 1024
MAGIC = {b'\xff\xd8\xff': 'image/jpeg', b'\x89PNG\r\n\x1a\n': 'image/png'}
LOCK = threading.Lock()
GAGAL_LOGIN = {}                    # ip -> [jumlah, waktu_blokir]

ROUTES = []

# Daftar menu sah per role. URL di luar daftar ini dialihkan ke dashboard role tsb.
# Harus sinkron dengan MENU di static/admin.js dan NAV di static/karyawan.js.
MENU_ADMIN = ('dashboard', 'karyawan', 'divisi', 'jobdesk', 'absensi',
              'lap-task', 'lap-hadir', 'monitor', 'set-jam', 'akun', 'profil')
MENU_KARYAWAN = ('dashboard', 'task', 'riwayat', 'profil')


def route(method, pattern, role='auth'):
    def deco(fn):
        ROUTES.append((method, re.compile(pattern), fn, role))
        return fn
    return deco


# ============================================================ util HTTP
class Resp:
    def __init__(self, status, payload, ctype=None):
        self.status = status
        self.payload = payload
        self.ctype = ctype


def ok(payload=None, status=200):
    """Respons sukses selalu menyertakan ok=true, digabung dengan payload."""
    if payload is None:
        return Resp(status, {'ok': True})
    if isinstance(payload, dict):
        d = {'ok': True}
        d.update(payload)
        return Resp(status, d)
    return Resp(status, payload)


def err(status, pesan, extra=None):
    d = {'ok': False, 'error': pesan}
    if extra:
        d.update(extra)
    return Resp(status, d)


def cek(cond, status, pesan):
    if not cond:
        raise ApiError(status, pesan)


class ApiError(Exception):
    def __init__(self, status, pesan):
        super().__init__(pesan)
        self.status = status
        self.pesan = pesan


# ============================================================ SERVER
class Handler(BaseHTTPRequestHandler):
    server_version = 'AbsensiServer/1.0'
    protocol_version = 'HTTP/1.1'

    # ---------- plumbing
    def log_message(self, fmt, *args):
        if os.environ.get('ABSENSI_VERBOSE'):
            sys.stderr.write('[%s] %s\n' % (self.log_date_time_string(), fmt % args))

    def _kirim(self, resp: Resp):
        if isinstance(resp.payload, bytes):
            body = resp.payload
            ctype = resp.ctype or 'application/octet-stream'
        else:
            body = json.dumps(resp.payload, ensure_ascii=False).encode('utf-8')
            ctype = 'application/json; charset=utf-8'
        self.send_response(resp.status)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'same-origin')
        if getattr(self, '_cookie_out', None):
            self.send_header('Set-Cookie', self._cookie_out)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def _cookie(self, nama, nilai, umur=60 * 60 * 12):
        bagian = '%s=%s; Path=/; HttpOnly; SameSite=Strict; Max-Age=%d' % (nama, nilai, umur)
        self._cookie_out = bagian

    def _hapus_cookie(self):
        self._cookie_out = 'sid=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0'

    def _cookies(self):
        raw = self.headers.get('Cookie', '')
        out = {}
        for bagian in raw.split(';'):
            if '=' in bagian:
                k, v = bagian.split('=', 1)
                out[k.strip()] = v.strip()
        return out

    def _body(self):
        try:
            panjang = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            panjang = 0
        if panjang <= 0:
            return {}
        cek(panjang <= MAX_BODY, 413, 'Ukuran data terlalu besar (maks 8 MB).')
        raw = self.rfile.read(panjang)
        try:
            return json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ApiError(400, 'Format JSON tidak valid.')

    def _query(self):
        return {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}

    def _ip(self):
        return self.client_address[0]

    # ---------- sesi
    def _sesi(self):
        token = self._cookies().get('sid')
        if not token:
            return None
        row = db.q("""SELECT s.token, s.csrf, s.expires_at, u.id AS user_id, u.username, u.role,
                             u.aktif, u.employee_id, e.nama, e.jabatan, e.division_id, e.foto_profil
                      FROM sessions s JOIN users u ON u.id = s.user_id
                      LEFT JOIN employees e ON e.id = u.employee_id
                      WHERE s.token = ?""", (token,), one=True)
        if not row:
            return None
        if row['expires_at'] < db.now_iso():
            db.x('DELETE FROM sessions WHERE token = ?', (token,))
            return None
        if not row['aktif']:
            return None
        return row

    def _wajib_login(self):
        s = self._sesi()
        cek(s is not None, 401, 'Sesi berakhir. Silakan login ulang.')
        return s

    def _csrf(self, s):
        if self.command in ('POST', 'PUT', 'DELETE', 'PATCH'):
            tok = self.headers.get('X-CSRF') or ''
            cek(bool(tok) and secrets.compare_digest(tok, s['csrf']), 403, 'Token CSRF tidak valid.')

    def _wajib_admin(self, s):
        cek(s['role'] == 'admin', 403, 'Akses ditolak. Menu ini hanya untuk admin.')

    def _emp_id(self, s):
        """ID karyawan milik sesi. Wajib ada untuk aksi karyawan."""
        cek(s['employee_id'] is not None, 403,
            'Akun ini tidak terhubung ke data karyawan. Hubungi admin.')
        emp = db.q('SELECT * FROM employees WHERE id = ?', (s['employee_id'],), one=True)
        cek(emp is not None, 403, 'Data karyawan untuk akun ini tidak ditemukan.')
        return emp['id']

    # ---------- dispatcher
    def _proses(self):
        self._cookie_out = None
        u = urlparse(self.path)
        jalur = u.path
        try:
            if jalur.startswith('/api/'):
                return self._api(jalur)
            return self._statis(jalur)
        except ApiError as e:
            return err(e.status, e.pesan)
        except Exception as e:                                  # noqa: BLE001
            if os.environ.get('ABSENSI_VERBOSE'):
                import traceback
                traceback.print_exc()
            return err(500, 'Kesalahan server: %s' % e)

    def _api(self, jalur):
        for method, pola, fn, role in ROUTES:
            if method != self.command:
                continue
            m = pola.match(jalur)
            if not m:
                continue
            body = self._body() if self.command in ('POST', 'PUT', 'DELETE', 'PATCH') else {}
            if role == 'public':
                return fn(self, m, body, None)
            s = self._wajib_login()
            self._csrf(s)
            if role == 'admin':
                self._wajib_admin(s)
            return fn(self, m, body, s)
        return err(404, 'Endpoint tidak ditemukan: %s' % jalur)

    def _statis(self, jalur):
        # ---- normalisasi
        jalur = '/' + jalur.strip('/')
        if jalur == '/index.html' or jalur == '/':
            s = self._sesi()
            if s:
                return self._redirect('/admin/dashboard' if s['role'] == 'admin' else '/employee/dashboard')
            return self._file(os.path.join(STATIC_DIR, 'index.html'))
        if jalur in ('/admin.html', '/karyawan.html', '/employee.html'):
            # berkas lama: diteruskan ke URL ber-role supaya guard role tetap berlaku
            return self._statis('/admin/dashboard' if jalur == '/admin.html' else '/employee/dashboard')

        bagian = [b for b in jalur.split('/') if b]

        # ---- /admin/<menu> : wajib sesi admin
        if bagian[0] == 'admin':
            s = self._sesi()
            if not s:
                return self._redirect('/?masuk=1')
            if s['role'] != 'admin':
                db.log(s['user_id'], 'akses_ditolak', 'karyawan membuka halaman admin: ' + jalur)
                return self._redirect('/employee/dashboard')
            menu = bagian[1] if len(bagian) > 1 else 'dashboard'
            if menu not in MENU_ADMIN:
                return self._redirect('/admin/dashboard')
            return self._file(os.path.join(STATIC_DIR, 'admin.html'))

        # ---- /employee/<menu> : hanya untuk karyawan
        if bagian[0] in ('employee', 'karyawan'):
            s = self._sesi()
            if not s:
                return self._redirect('/?masuk=1')
            if s['role'] == 'admin':
                return self._redirect('/admin/dashboard')
            menu = bagian[1] if len(bagian) > 1 else 'dashboard'
            if menu not in MENU_KARYAWAN:
                return self._redirect('/employee/dashboard')
            return self._file(os.path.join(STATIC_DIR, 'karyawan.html'))

        if jalur.startswith('/static/'):
            rel = unquote(jalur[len('/static/'):])
            target = os.path.normpath(os.path.join(STATIC_DIR, rel))
            cek(target.startswith(STATIC_DIR), 403, 'Akses ditolak.')
            return self._file(target)
        if jalur == '/favicon.ico':
            return Resp(204, b'', 'image/x-icon')
        return err(404, 'Halaman tidak ditemukan.')

    def _redirect(self, ke):
        r = Resp(302, b'', 'text/plain')
        self._redirect_to = ke
        return r

    def _file(self, path):
        if not os.path.isfile(path):
            return err(404, 'File tidak ditemukan.')
        with open(path, 'rb') as f:
            data = f.read()
        ctype = mimetypes.guess_type(path)[0] or 'application/octet-stream'
        if path.endswith(('.html', '.css', '.js')):
            ctype += '; charset=utf-8'
        return Resp(200, data, ctype)

    # ---------- verb
    def _jalan(self):
        try:
            resp = self._proses()
        except ApiError as e:
            resp = err(e.status, e.pesan)
        except Exception as e:                                       # noqa: BLE001
            import traceback
            traceback.print_exc()
            resp = err(500, 'Kesalahan server: %s' % e)
        if getattr(self, '_redirect_to', None):
            self.send_response(302)
            self.send_header('Location', self._redirect_to)
            self.send_header('Content-Length', '0')
            self._redirect_to = None
            self.end_headers()
            return
        self._kirim(resp)

    def do_GET(self):
        self._jalan()

    def do_HEAD(self):
        self._jalan()

    def do_POST(self):
        self._jalan()

    def do_PUT(self):
        self._jalan()

    def do_DELETE(self):
        self._jalan()


# ============================================================ AUTH
@route('POST', r'^/api/login$', 'public')
def api_login(h, m, body, s):
    ip = h._ip()
    with LOCK:
        info = GAGAL_LOGIN.get(ip)
        if info and info[0] >= 8:
            cek(db.now().timestamp() > info[1], 429, 'Terlalu banyak percobaan gagal. Coba lagi beberapa menit.')
            GAGAL_LOGIN.pop(ip, None)

    username = str(body.get('username', '')).strip().lower()
    password = str(body.get('password', ''))
    cek(username and password, 400, 'Username dan password wajib diisi.')

    u = db.q('SELECT * FROM users WHERE lower(username) = ?', (username,), one=True)
    if not u or not db.verify_password(password, u['password_hash'], u['salt']):
        with LOCK:
            info = GAGAL_LOGIN.setdefault(ip, [0, 0])
            info[0] += 1
            info[1] = db.now().timestamp() + 300
        db.log(None, 'login_gagal', 'username=%s ip=%s' % (username, ip))
        raise ApiError(401, 'Username atau password salah.')
    cek(u['aktif'] == 1, 403, 'Akun dinonaktifkan. Hubungi admin.')
    if u['role'] == 'karyawan':
        emp = db.q('SELECT status FROM employees WHERE id = ?', (u['employee_id'],), one=True)
        cek(emp and emp['status'] == 'aktif', 403, 'Status karyawan nonaktif. Hubungi admin.')

    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(24)
    exp = (db.now() + dt.timedelta(hours=12)).strftime('%Y-%m-%d %H:%M:%S')
    db.x('INSERT INTO sessions (token, user_id, csrf, created_at, expires_at, ip, user_agent) VALUES (?,?,?,?,?,?,?)',
         (token, u['id'], csrf, db.now_iso(), exp, ip, h.headers.get('User-Agent', '')[:200]))
    db.x('UPDATE users SET last_login = ? WHERE id = ?', (db.now_iso(), u['id']))
    db.x('DELETE FROM sessions WHERE expires_at < ?', (db.now_iso(),))
    db.log(u['id'], 'login', 'ip=%s' % ip)
    with LOCK:
        GAGAL_LOGIN.pop(ip, None)
    h._cookie('sid', token, 12 * 3600)
    return ok({'user': _user_dto(u), 'csrf': csrf})


@route('POST', r'^/api/logout$')
def api_logout(h, m, body, s):
    h._hapus_cookie()
    db.x('DELETE FROM sessions WHERE token = ?', (h._cookies().get('sid'),))
    db.log(s['user_id'], 'logout')
    return ok()


def _user_dto(u, emp=None):
    return {
        'id': u['id'], 'username': u['username'], 'role': u['role'], 'email': u.get('email', ''),
        'employee_id': u.get('employee_id'), 'nama': u.get('nama') or u['username'],
        'jabatan': u.get('jabatan') or '', 'aktif': u.get('aktif', 1),
        'foto_profil': (emp or u).get('foto_profil', '') or '',
    }


@route('GET', r'^/api/me$')
def api_me(h, m, body, s):
    set_ = db.settings()
    return ok({'user': {k: s[k] for k in ('user_id', 'username', 'role', 'employee_id', 'nama', 'jabatan')},
               'csrf': s['csrf'], 'settings': _set_dto(set_), 'jam_server': db.now_iso()})


def _set_dto(x):
    return {'nama_instansi': x['nama_instansi'], 'jam_masuk': x['jam_masuk'], 'jam_pulang': x['jam_pulang'],
            'toleransi_menit': x['toleransi_menit'], 'hari_kerja': x['hari_kerja'],
            'zona_waktu': x['zona_waktu'], 'wajib_foto': x['wajib_foto'], 'updated_at': x['updated_at']}


# ============================================================ MASTER DATA
@route('GET', r'^/api/divisions$')
def api_div_get(h, m, body, s):
    return ok({'data': db.q("""SELECT d.*, (SELECT COUNT(*) FROM employees e WHERE e.division_id = d.id) AS jml_karyawan
                              FROM divisions d ORDER BY d.nama""")})


@route('POST', r'^/api/divisions$', 'admin')
def api_div_post(h, m, body, s):
    nama = str(body.get('nama', '')).strip()
    cek(len(nama) >= 2, 400, 'Nama divisi minimal 2 karakter.')
    cek(not db.q('SELECT id FROM divisions WHERE lower(nama) = lower(?)', (nama,), one=True), 409, 'Divisi sudah ada.')
    i = db.x('INSERT INTO divisions (nama, keterangan, created_at) VALUES (?,?,?)',
             (nama, str(body.get('keterangan', '')).strip(), db.now_iso()))
    db.log(s['user_id'], 'divisi_baru', nama)
    return ok({'id': i})


@route('PUT', r'^/api/divisions/(?P<id>\d+)$', 'admin')
def api_div_put(h, m, body, s):
    did = int(m.group('id'))
    cek(db.q('SELECT id FROM divisions WHERE id = ?', (did,), one=True), 404, 'Divisi tidak ditemukan.')
    db.x('UPDATE divisions SET nama = ?, keterangan = ? WHERE id = ?',
         (str(body.get('nama', '')).strip(), str(body.get('keterangan', '')).strip(), did))
    return ok()


@route('DELETE', r'^/api/divisions/(?P<id>\d+)$', 'admin')
def api_div_del(h, m, body, s):
    did = int(m.group('id'))
    dipakai = db.q('SELECT COUNT(*) AS c FROM employees WHERE division_id = ?', (did,), one=True)['c']
    cek(dipakai == 0, 409, 'Divisi masih dipakai %d karyawan.' % dipakai)
    db.x('DELETE FROM divisions WHERE id = ?', (did,))
    return ok()


# ------------------------------------------------------------ karyawan
@route('GET', r'^/api/employees$')
def api_emp_get(h, m, body, s):
    if s['role'] != 'admin':
        emp = db.q("""SELECT e.*, d.nama AS divisi, u.username FROM employees e
                      LEFT JOIN divisions d ON d.id = e.division_id
                      LEFT JOIN users u ON u.employee_id = e.id WHERE e.id = ?""", (s['employee_id'],))
        return ok({'data': emp})
    qs = h._query()
    sql = """SELECT e.*, d.nama AS divisi, u.username, u.aktif AS akun_aktif, u.last_login
             FROM employees e LEFT JOIN divisions d ON d.id = e.division_id
             LEFT JOIN users u ON u.employee_id = e.id WHERE 1=1"""
    args = []
    if qs.get('q'):
        sql += ' AND (e.nama LIKE ? OR e.nik LIKE ? OR e.jabatan LIKE ?)'
        args += ['%' + qs['q'] + '%'] * 3
    if qs.get('division_id'):
        sql += ' AND e.division_id = ?'
        args.append(int(qs['division_id']))
    if qs.get('status'):
        sql += ' AND e.status = ?'
        args.append(qs['status'])
    sql += ' ORDER BY e.nama'
    return ok({'data': db.q(sql, args)})


@route('POST', r'^/api/employees$', 'admin')
def api_emp_post(h, m, body, s):
    nama = str(body.get('nama', '')).strip()
    cek(len(nama) >= 2, 400, 'Nama karyawan minimal 2 karakter.')
    nik = str(body.get('nik', '')).strip()
    if nik:
        cek(not db.q('SELECT id FROM employees WHERE nik = ?', (nik,), one=True), 409, 'NIK sudah dipakai.')
    did = body.get('division_id') or None
    i = db.x("""INSERT INTO employees (nama, nik, email, telepon, jabatan, division_id, tgl_masuk, status, created_at)
                VALUES (?,?,?,?,?,?,?,?,?)""",
             (nama, nik, str(body.get('email', '')).strip(), str(body.get('telepon', '')).strip(),
              str(body.get('jabatan', '')).strip(), did, str(body.get('tgl_masuk', '')).strip(),
              body.get('status', 'aktif'), db.now_iso()))
    hasil = {'id': i}
    if body.get('buat_akun'):
        u, pw = _buat_akun_karyawan(i, body.get('username'), body.get('password'))
        hasil['akun'] = u
        hasil['password_awal'] = pw
    db.log(s['user_id'], 'karyawan_baru', nama)
    return ok(hasil)


def _buat_akun_karyawan(employee_id, username=None, password=None):
    emp = db.q('SELECT * FROM employees WHERE id = ?', (employee_id,), one=True)
    cek(emp is not None, 404, 'Karyawan tidak ditemukan.')
    cek(not db.q('SELECT id FROM users WHERE employee_id = ?', (employee_id,), one=True), 409,
        'Karyawan ini sudah punya akun login.')
    username = (username or emp['nama'].split()[0]).strip().lower()
    username = re.sub(r'[^a-z0-9._]', '', username) or 'user%d' % employee_id
    dasar = username
    n = 1
    while db.q('SELECT id FROM users WHERE lower(username) = ?', (username,), one=True):
        n += 1
        username = '%s%d' % (dasar, n)
    pw = password or secrets.token_urlsafe(6)
    cek(len(pw) >= 6, 400, 'Password minimal 6 karakter.')
    h, salt = db.hash_password(pw)
    db.x("""INSERT INTO users (username, email, password_hash, salt, role, employee_id, aktif, created_at)
            VALUES (?,?,?,?,'karyawan',?,1,?)""", (username, emp['email'], h, salt, employee_id, db.now_iso()))
    return username, pw


@route('POST', r'^/api/employees/(?P<id>\d+)/akun$', 'admin')
def api_emp_akun(h, m, body, s):
    eid = int(m.group('id'))
    u, pw = _buat_akun_karyawan(eid, body.get('username'), body.get('password'))
    db.log(s['user_id'], 'akun_dibuat', 'employee=%s username=%s' % (eid, u))
    return ok({'username': u, 'password_awal': pw})


@route('PUT', r'^/api/employees/(?P<id>\d+)$', 'admin')
def api_emp_put(h, m, body, s):
    eid = int(m.group('id'))
    cek(db.q('SELECT id FROM employees WHERE id = ?', (eid,), one=True), 404, 'Karyawan tidak ditemukan.')
    nama = str(body.get('nama', '')).strip()
    cek(len(nama) >= 2, 400, 'Nama karyawan minimal 2 karakter.')
    nik = str(body.get('nik', '')).strip()
    if nik:
        cek(not db.q('SELECT id FROM employees WHERE nik = ? AND id <> ?', (nik, eid), one=True), 409, 'NIK sudah dipakai.')
    db.x("""UPDATE employees SET nama=?, nik=?, email=?, telepon=?, jabatan=?, division_id=?,
            tgl_masuk=?, status=? WHERE id=?""",
         (nama, nik, str(body.get('email', '')).strip(), str(body.get('telepon', '')).strip(),
          str(body.get('jabatan', '')).strip(), body.get('division_id') or None,
          str(body.get('tgl_masuk', '')).strip(), body.get('status', 'aktif'), eid))
    if body.get('password'):
        _ganti_password_karyawan(eid, body['password'])
    db.log(s['user_id'], 'karyawan_edit', nama)
    return ok()


def _ganti_password_karyawan(employee_id, baru):
    cek(len(str(baru)) >= 6, 400, 'Password minimal 6 karakter.')
    u = db.q('SELECT id FROM users WHERE employee_id = ?', (employee_id,), one=True)
    cek(u is not None, 404, 'Akun login karyawan ini belum dibuat.')
    h, salt = db.hash_password(baru)
    db.x('UPDATE users SET password_hash=?, salt=? WHERE id=?', (h, salt, u['id']))
    db.x('DELETE FROM sessions WHERE user_id = ?', (u['id'],))


@route('DELETE', r'^/api/employees/(?P<id>\d+)$', 'admin')
def api_emp_del(h, m, body, s):
    eid = int(m.group('id'))
    emp = db.q('SELECT nama FROM employees WHERE id = ?', (eid,), one=True)
    cek(emp is not None, 404, 'Karyawan tidak ditemukan.')
    for f in db.q("""SELECT p.file_path FROM attendance_photos p JOIN attendance a ON a.id = p.attendance_id
                     WHERE a.employee_id = ?""", (eid,)):
        try:
            os.remove(f['file_path'])
        except OSError:
            pass
    db.x('DELETE FROM employees WHERE id = ?', (eid,))
    db.log(s['user_id'], 'karyawan_hapus', emp['nama'])
    return ok()


# ------------------------------------------------------------ akun
@route('GET', r'^/api/users$', 'admin')
def api_users(h, m, body, s):
    return ok({'data': db.q("""SELECT u.id, u.username, u.email, u.role, u.aktif, u.employee_id,
                                      u.last_login, e.nama FROM users u
                               LEFT JOIN employees e ON e.id = u.employee_id ORDER BY u.role, u.username""")})


@route('PUT', r'^/api/users/(?P<id>\d+)$', 'admin')
def api_user_put(h, m, body, s):
    uid = int(m.group('id'))
    u = db.q('SELECT * FROM users WHERE id = ?', (uid,), one=True)
    cek(u is not None, 404, 'Akun tidak ditemukan.')
    cek(not (uid == s['user_id'] and body.get('aktif') in (0, False)), 400, 'Tidak bisa menonaktifkan akun sendiri.')
    if 'aktif' in body:
        db.x('UPDATE users SET aktif = ? WHERE id = ?', (1 if body['aktif'] else 0, uid))
        if not body['aktif']:
            db.x('DELETE FROM sessions WHERE user_id = ?', (uid,))
    if body.get('password'):
        cek(len(str(body['password'])) >= 6, 400, 'Password minimal 6 karakter.')
        h_, salt = db.hash_password(body['password'])
        db.x('UPDATE users SET password_hash=?, salt=? WHERE id=?', (h_, salt, uid))
        db.x('DELETE FROM sessions WHERE user_id = ?', (uid,))
    if body.get('username'):
        baru = re.sub(r'[^a-z0-9._]', '', str(body['username']).strip().lower())
        cek(len(baru) >= 3, 400, 'Username minimal 3 karakter (huruf/angka/titik).')
        cek(not db.q('SELECT id FROM users WHERE lower(username)=? AND id<>?', (baru, uid), one=True), 409, 'Username sudah dipakai.')
        db.x('UPDATE users SET username = ? WHERE id = ?', (baru, uid))
    db.log(s['user_id'], 'akun_edit', 'user=%s' % uid)
    return ok()


# ------------------------------------------------------------ jobdesk
@route('GET', r'^/api/jobdesks$')
def api_jd_get(h, m, body, s):
    qs = h._query()
    sql = """SELECT j.*, d.nama AS divisi FROM jobdesks j LEFT JOIN divisions d ON d.id = j.division_id WHERE 1=1"""
    args = []
    if qs.get('division_id'):
        sql += ' AND j.division_id = ?'
        args.append(int(qs['division_id']))
    if qs.get('kategori'):
        sql += ' AND j.kategori = ?'
        args.append(qs['kategori'])
    if qs.get('aktif') in ('0', '1'):
        sql += ' AND j.aktif = ?'
        args.append(int(qs['aktif']))
    if s['role'] != 'admin':
        sql += ' AND j.aktif = 1'
    sql += ' ORDER BY j.urutan, j.id'
    return ok({'data': db.q(sql, args),
               'kategori': [r['kategori'] for r in db.q("SELECT DISTINCT kategori FROM jobdesks WHERE kategori <> '' ORDER BY kategori")]})


@route('POST', r'^/api/jobdesks$', 'admin')
def api_jd_post(h, m, body, s):
    judul = str(body.get('judul', '')).strip()
    cek(len(judul) >= 3, 400, 'Judul jobdesk minimal 3 karakter.')
    urut = db.q('SELECT COALESCE(MAX(urutan), 0) + 1 AS u FROM jobdesks', one=True)['u']
    i = db.x("""INSERT INTO jobdesks (judul, kategori, division_id, deskripsi, aktif, urutan, created_at)
                VALUES (?,?,?,?,?,?,?)""",
             (judul, str(body.get('kategori', '')).strip(), body.get('division_id') or None,
              str(body.get('deskripsi', '')).strip(), 1 if body.get('aktif', 1) else 0, urut, db.now_iso()))
    db.log(s['user_id'], 'jobdesk_baru', judul)
    return ok({'id': i})


@route('PUT', r'^/api/jobdesks/(?P<id>\d+)$', 'admin')
def api_jd_put(h, m, body, s):
    jid = int(m.group('id'))
    cek(db.q('SELECT id FROM jobdesks WHERE id = ?', (jid,), one=True), 404, 'Jobdesk tidak ditemukan.')
    judul = str(body.get('judul', '')).strip()
    cek(len(judul) >= 3, 400, 'Judul jobdesk minimal 3 karakter.')
    db.x("""UPDATE jobdesks SET judul=?, kategori=?, division_id=?, deskripsi=?, aktif=? WHERE id=?""",
         (judul, str(body.get('kategori', '')).strip(), body.get('division_id') or None,
          str(body.get('deskripsi', '')).strip(), 1 if body.get('aktif', 1) else 0, jid))
    return ok()


@route('DELETE', r'^/api/jobdesks/(?P<id>\d+)$', 'admin')
def api_jd_del(h, m, body, s):
    jid = int(m.group('id'))
    db.x('DELETE FROM jobdesks WHERE id = ?', (jid,))
    db.log(s['user_id'], 'jobdesk_hapus', str(jid))
    return ok()


# ============================================================ ABSENSI
def _validasi_foto(data_url):
    """
    Validasi foto SEBELUM ada data absensi yang ditulis.
    Foto wajib diunggah lebih dulu; absensi baru disimpan setelah foto sah.
    Return (bytes_gambar, mime).
    """
    cek(isinstance(data_url, str) and data_url.startswith('data:image/'), 400,
        'Foto wajib diunggah langsung dari kamera.')
    try:
        head, b64 = data_url.split(',', 1)
        mime = head.split(';')[0].replace('data:', '')
        raw = base64.b64decode(b64, validate=True)
    except (ValueError, binascii.Error):
        raise ApiError(400, 'Data foto tidak valid.')
    cek(mime in ('image/jpeg', 'image/png', 'image/webp'), 400, 'Format foto harus JPEG/PNG/WEBP.')
    cek(len(raw) <= MAX_FOTO, 413, 'Ukuran foto terlalu besar (maks 6 MB).')
    cek(len(raw) >= 2048, 400, 'Foto terlalu kecil / rusak. Ambil ulang dari kamera.')
    cek(any(raw.startswith(m) for m in MAGIC), 400, 'Isi file bukan gambar yang sah.')
    return raw, mime


def _simpan_foto(attendance_id, jenis, raw, mime):
    cek(not db.q('SELECT id FROM attendance_photos WHERE attendance_id = ? AND jenis = ?', (attendance_id, jenis), one=True),
        409, 'Foto %s untuk absensi ini sudah ada.' % jenis)
    sub = os.path.join(FOTO_DIR, db.today()[:7])
    os.makedirs(sub, exist_ok=True)
    nama = 'att%d_%s_%s.%s' % (attendance_id, jenis, secrets.token_hex(6),
                              'png' if raw.startswith(b'\x89PNG') else 'jpg')
    path = os.path.join(sub, nama)
    with open(path, 'wb') as f:
        f.write(raw)
    pid = db.x("""INSERT INTO attendance_photos (attendance_id, jenis, file_path, mime, size, created_at)
                  VALUES (?,?,?,?,?,?)""", (attendance_id, jenis, path, mime, len(raw), db.now_iso()))
    return {'id': pid, 'jenis': jenis, 'size': len(raw), 'mime': mime}


@route('POST', r'^/api/attendance/masuk$')
def api_masuk(h, m, body, s):
    cek(s['role'] == 'karyawan' or s['employee_id'], 403, 'Hanya karyawan yang bisa absen.')
    eid = h._emp_id(s)
    set_ = db.settings()
    tanggal = db.today()
    lama = db.q('SELECT * FROM attendance WHERE employee_id = ? AND tanggal = ?', (eid, tanggal), one=True)
    cek(not (lama and lama['checkin_at']), 409, 'Anda sudah absen masuk hari ini pada pukul %s.' % (lama or {}).get('checkin_at', ''))

    # FOTO DULU: divalidasi sebelum ada data absensi yang ditulis.
    if body.get('foto'):
        raw, mime = _validasi_foto(body['foto'])
    else:
        cek(not set_['wajib_foto'], 400, 'Foto wajib diunggah sebelum absensi disimpan.')
        raw = mime = None

    sekarang = db.now()                                  # <-- waktu server, bukan dari client
    status, telat = db.hitung_status_masuk(sekarang.hour * 60 + sekarang.minute, set_)
    if lama:
        att_id = lama['id']
        db.x("""UPDATE attendance SET checkin_at=?, checkin_epoch=?, status=?, terlambat_menit=?,
                catatan=?, sumber='server' WHERE id=?""",
             (sekarang.strftime('%Y-%m-%d %H:%M:%S'), int(sekarang.timestamp()), status, telat,
              str(body.get('catatan', '')).strip()[:300], att_id))
    else:
        att_id = db.x("""INSERT INTO attendance (employee_id, tanggal, checkin_at, checkin_epoch, status,
                          terlambat_menit, catatan, sumber) VALUES (?,?,?,?,?,?,?,'server')""",
                      (eid, tanggal, sekarang.strftime('%Y-%m-%d %H:%M:%S'), int(sekarang.timestamp()),
                       status, telat, str(body.get('catatan', '')).strip()[:300]))
    foto = _simpan_foto(att_id, 'checkin', raw, mime) if raw else None
    db.log(s['user_id'], 'absen_masuk', 'employee=%s status=%s' % (eid, status))
    return ok({'attendance': _att_dto(db.q('SELECT * FROM attendance WHERE id = ?', (att_id,), one=True)),
               'status': status, 'terlambat_menit': telat, 'waktu_server': sekarang.strftime('%H:%M:%S'),
               'foto': foto})


@route('POST', r'^/api/attendance/pulang$')
def api_pulang(h, m, body, s):
    eid = h._emp_id(s)
    set_ = db.settings()
    row = db.q('SELECT * FROM attendance WHERE employee_id = ? AND tanggal = ?', (eid, db.today()), one=True)
    cek(row is not None and row['checkin_at'], 400, 'Belum absen masuk hari ini.')
    cek(not row['checkout_at'], 409, 'Anda sudah absen pulang hari ini pada pukul %s.' % row['checkout_at'])

    # FOTO DULU: divalidasi sebelum jam pulang disimpan.
    if body.get('foto'):
        raw, mime = _validasi_foto(body['foto'])
    else:
        cek(not set_['wajib_foto'], 400, 'Foto wajib diunggah sebelum absensi disimpan.')
        raw = mime = None

    sekarang = db.now()
    durasi = int((sekarang.timestamp() - (row['checkin_epoch'] or 0)) // 60)
    db.x("""UPDATE attendance SET checkout_at=?, checkout_epoch=?, durasi_menit=?, sumber='server' WHERE id=?""",
         (sekarang.strftime('%Y-%m-%d %H:%M:%S'), int(sekarang.timestamp()), durasi, row['id']))
    foto = _simpan_foto(row['id'], 'checkout', raw, mime) if raw else None
    db.log(s['user_id'], 'absen_pulang', 'employee=%s durasi=%s menit' % (eid, durasi))
    return ok({'attendance': _att_dto(db.q('SELECT * FROM attendance WHERE id = ?', (row['id'],), one=True)),
               'waktu_server': sekarang.strftime('%H:%M:%S'), 'foto': foto})


def _att_dto(a, emp=None, set_=None):
    if a is None:
        return None
    d = dict(a)
    d['status_tampil'] = db.status_absensi(a, set_ or db.settings())
    d['durasi_jam'] = round((a.get('durasi_menit') or 0) / 60, 2) if a.get('durasi_menit') is not None else None
    if emp:
        d['nama'] = emp['nama']
        d['nik'] = emp['nik']
        d['jabatan'] = emp['jabatan']
        d['divisi'] = emp.get('divisi') or ''
        d['division_id'] = emp.get('division_id')
    return d


@route('GET', r'^/api/attendance/hari-ini$')
def api_att_hari_ini(h, m, body, s):
    eid = h._emp_id(s)
    row = db.q('SELECT * FROM attendance WHERE employee_id = ? AND tanggal = ?', (eid, db.today()), one=True)
    return ok({'attendance': _att_dto(row) if row else None, 'tanggal': db.today(),
               'jam_server': db.now().strftime('%H:%M:%S')})


@route('GET', r'^/api/attendance$')
def api_att_get(h, m, body, s):
    qs = h._query()
    sql = """SELECT a.*, e.nama, e.nik, e.jabatan, e.division_id, d.nama AS divisi FROM attendance a
             JOIN employees e ON e.id = a.employee_id
             LEFT JOIN divisions d ON d.id = e.division_id WHERE 1=1"""
    args = []
    if s['role'] != 'admin':
        sql += ' AND a.employee_id = ?'
        args.append(s['employee_id'])
    if qs.get('employee_id'):
        sql += ' AND a.employee_id = ?'
        args.append(int(qs['employee_id']))
    if qs.get('division_id'):
        sql += ' AND e.division_id = ?'
        args.append(int(qs['division_id']))
    if qs.get('from'):
        sql += ' AND a.tanggal >= ?'
        args.append(qs['from'])
    if qs.get('to'):
        sql += ' AND a.tanggal <= ?'
        args.append(qs['to'])
    if qs.get('tanggal'):
        sql += ' AND a.tanggal = ?'
        args.append(qs['tanggal'])
    if qs.get('q'):
        sql += ' AND e.nama LIKE ?'
        args.append('%' + qs['q'] + '%')
    if qs.get('status') == 'telat':
        sql += " AND a.status = 'Terlambat'"
    elif qs.get('status') == 'pulang':
        sql += ' AND a.checkout_at IS NOT NULL'
    elif qs.get('status') == 'belum_pulang':
        sql += ' AND a.checkin_at IS NOT NULL AND a.checkout_at IS NULL'
    sql += ' ORDER BY a.tanggal DESC, e.nama LIMIT 1000'
    set_ = db.settings()
    data = []
    for r in db.q(sql, args):
        foto = {f['jenis']: f['id'] for f in db.q(
            'SELECT id, jenis FROM attendance_photos WHERE attendance_id = ?', (r['id'],))}
        d = _att_dto(r, r, set_)
        d['foto'] = foto
        d['foto_masuk'] = foto.get('checkin')
        d['foto_pulang'] = foto.get('checkout')
        data.append(d)
    return ok({'data': data})


@route('GET', r'^/api/photo/(?P<id>\d+)$')
def api_photo(h, m, body, s):
    pid = int(m.group('id'))
    p = db.q("""SELECT p.*, a.employee_id FROM attendance_photos p
                JOIN attendance a ON a.id = p.attendance_id WHERE p.id = ?""", (pid,), one=True)
    cek(p is not None, 404, 'Foto tidak ditemukan.')
    if s['role'] != 'admin':
        cek(s['employee_id'] == p['employee_id'], 403, 'Anda tidak berhak melihat foto ini.')
    cek(os.path.isfile(p['file_path']), 404, 'File foto sudah tidak ada di storage.')
    with open(p['file_path'], 'rb') as f:
        return Resp(200, f.read(), p['mime'])


# ============================================================ TASK HARIAN
@route('GET', r'^/api/tasks$')
def api_task_get(h, m, body, s):
    qs = h._query()
    tanggal = qs.get('tanggal') or db.today()
    cek(re.match(r'^\d{4}-\d{2}-\d{2}$', tanggal), 400, 'Format tanggal harus YYYY-MM-DD.')
    if s['role'] == 'admin':
        eid = int(qs.get('employee_id') or 0)
        cek(eid > 0, 400, 'Pilih karyawan terlebih dahulu.')
        own = False
    else:
        eid = h._emp_id(s)
        own = True
    emp = db.q("""SELECT e.*, d.nama AS divisi FROM employees e LEFT JOIN divisions d ON d.id = e.division_id
                  WHERE e.id = ?""", (eid,), one=True)
    cek(emp is not None, 404, 'Karyawan tidak ditemukan.')
    jd = db.jobdesk_untuk(eid)
    tsel = {t['jobdesk_id']: t for t in db.q(
        'SELECT * FROM daily_tasks WHERE employee_id = ? AND tanggal = ?', (eid, tanggal))}
    data = []
    for j in jd:
        t = tsel.get(j['id'])
        data.append({**j, 'jobdesk_id': j['id'], 'selesai': (t or {}).get('selesai', 0),
                     'waktu_selesai': (t or {}).get('waktu_selesai'), 'task_id': (t or {}).get('id')})
    selesai = sum(1 for d in data if d['selesai'])
    return ok({'tanggal': tanggal, 'karyawan': {'id': emp['id'], 'nama': emp['nama'], 'jabatan': emp['jabatan'],
                                                'divisi': emp['divisi'] or ''},
               'data': data, 'selesai': selesai, 'total': len(data),
               'persen': round(selesai * 100 / len(data)) if data else 0,
               'boleh_ubah': (not own) or tanggal == db.today()})


@route('POST', r'^/api/tasks/toggle$')
def api_task_toggle(h, m, body, s):
    tanggal = str(body.get('tanggal') or db.today())
    cek(re.match(r'^\d{4}-\d{2}-\d{2}$', tanggal), 400, 'Format tanggal harus YYYY-MM-DD.')
    jid = int(body.get('jobdesk_id') or 0)
    cek(jid > 0, 400, 'Jobdesk tidak valid.')
    selesai = 1 if body.get('selesai') else 0
    if s['role'] == 'admin':
        eid = int(body.get('employee_id') or 0)
        cek(eid > 0, 400, 'Pilih karyawan terlebih dahulu.')
    else:
        eid = h._emp_id(s)
        cek(tanggal == db.today(), 403, 'Anda hanya dapat mengisi checklist untuk hari ini.')
    cek(db.q('SELECT id FROM jobdesks WHERE id = ? AND aktif = 1', (jid,), one=True), 404,
        'Jobdesk tidak ditemukan atau sudah tidak aktif.')
    cek(any(j['id'] == jid for j in db.jobdesk_untuk(eid)), 403, 'Jobdesk ini bukan untuk divisi Anda.')

    t = db.q('SELECT * FROM daily_tasks WHERE employee_id=? AND jobdesk_id=? AND tanggal=?', (eid, jid, tanggal), one=True)
    waktu = db.now_iso() if selesai else None
    if t:
        db.x('UPDATE daily_tasks SET selesai=?, waktu_selesai=? WHERE id=?', (selesai, waktu, t['id']))
        tid = t['id']
    else:
        tid = db.x("""INSERT INTO daily_tasks (employee_id, jobdesk_id, tanggal, selesai, waktu_selesai)
                      VALUES (?,?,?,?,?)""", (eid, jid, tanggal, selesai, waktu))
    db.log(s['user_id'], 'task_%s' % ('selesai' if selesai else 'batal'), 'jobdesk=%s tgl=%s emp=%s' % (jid, tanggal, eid))
    return ok({'id': tid, 'selesai': selesai, 'waktu_selesai': waktu})


@route('GET', r'^/api/tasks/riwayat$')
def api_task_riwayat(h, m, body, s):
    qs = h._query()
    dari = qs.get('from') or (db.now() - dt.timedelta(days=13)).strftime('%Y-%m-%d')
    sampai = qs.get('to') or db.today()
    if s['role'] == 'admin':
        sql = """SELECT t.tanggal, e.id AS employee_id, e.nama, e.jabatan, d.nama AS divisi,
                        SUM(t.selesai) AS selesai, COUNT(t.id) AS tercatat,
                        (SELECT COUNT(*) FROM jobdesks j WHERE j.aktif = 1 AND (j.division_id IS NULL OR j.division_id = e.division_id)) AS target
                 FROM daily_tasks t JOIN employees e ON e.id = t.employee_id
                 LEFT JOIN divisions d ON d.id = e.division_id
                 WHERE t.tanggal BETWEEN ? AND ?"""
        args = [dari, sampai]
        if qs.get('division_id'):
            sql += ' AND e.division_id = ?'
            args.append(int(qs['division_id']))
        if qs.get('q'):
            sql += ' AND e.nama LIKE ?'
            args.append('%' + qs['q'] + '%')
        if qs.get('employee_id'):
            sql += ' AND e.id = ?'
            args.append(int(qs['employee_id']))
        sql += ' GROUP BY t.tanggal, e.id ORDER BY t.tanggal DESC, e.nama'
        return ok({'data': db.q(sql, args), 'from': dari, 'to': sampai})
    eid = h._emp_id(s)
    sql = """SELECT t.tanggal, j.judul, j.kategori, t.selesai, t.waktu_selesai
             FROM daily_tasks t JOIN jobdesks j ON j.id = t.jobdesk_id
             WHERE t.employee_id = ? AND t.tanggal BETWEEN ? AND ?
             ORDER BY t.tanggal DESC, j.urutan"""
    return ok({'data': db.q(sql, (eid, dari, sampai)), 'from': dari, 'to': sampai})


# ============================================================ DASHBOARD
@route('GET', r'^/api/dashboard/admin$')
def api_dash_admin(h, m, body, s):
    h._wajib_admin(s)
    tanggal = h._query().get('tanggal') or db.today()
    set_ = db.settings()
    kar = db.q("""SELECT e.id, e.nama, e.nik, e.jabatan, e.division_id, d.nama AS divisi,
                         a.id AS att_id, a.checkin_at, a.checkout_at, a.status, a.terlambat_menit,
                         a.durasi_menit,
                         (SELECT id FROM attendance_photos p WHERE p.attendance_id = a.id AND p.jenis='checkin') AS foto_masuk,
                         (SELECT id FROM attendance_photos p WHERE p.attendance_id = a.id AND p.jenis='checkout') AS foto_pulang
                  FROM employees e LEFT JOIN divisions d ON d.id = e.division_id
                  LEFT JOIN attendance a ON a.employee_id = e.id AND a.tanggal = ?
                  WHERE e.status = 'aktif' ORDER BY e.nama""", (tanggal,))
    rows = []
    sudah = belum = telat = pulang = 0
    for k in kar:
        status = db.status_absensi({'checkout_at': k['checkout_at'], 'status': k['status']} if k['checkin_at'] else None, set_)
        if k['checkin_at']:
            sudah += 1
            if status == 'Terlambat':
                telat += 1
            if k['checkout_at']:
                pulang += 1
        else:
            belum += 1
        target = len(db.jobdesk_untuk(k['id']))
        selesai = db.q('SELECT COUNT(*) AS c FROM daily_tasks WHERE employee_id=? AND tanggal=? AND selesai=1',
                       (k['id'], tanggal), one=True)['c']
        rows.append({**k, 'status_tampil': status, 'task_selesai': selesai, 'task_target': target,
                     'task_persen': round(selesai * 100 / target) if target else 0})
    task_selesai = sum(r['task_selesai'] for r in rows)
    task_target = sum(r['task_target'] for r in rows)
    return ok({'tanggal': tanggal, 'jam_server': db.now().strftime('%H:%M:%S'),
               'ringkasan': {'total_karyawan': len(rows), 'sudah_absen': sudah, 'belum_absen': belum,
                             'terlambat': telat, 'sudah_pulang': pulang,
                             'task_selesai': task_selesai, 'task_target': task_target,
                             'task_persen': round(task_selesai * 100 / task_target) if task_target else 0},
               'karyawan': rows,
               'aktivitas': db.q("""SELECT l.created_at, l.aksi, l.detail, u.username FROM activity_log l
                                    LEFT JOIN users u ON u.id = l.user_id
                                    ORDER BY l.id DESC LIMIT 8"""),
               'settings': _set_dto(set_)})


@route('GET', r'^/api/dashboard/karyawan$')
def api_dash_karyawan(h, m, body, s):
    eid = h._emp_id(s)
    set_ = db.settings()
    tanggal = db.today()
    emp = db.q("""SELECT e.*, d.nama AS divisi FROM employees e LEFT JOIN divisions d ON d.id = e.division_id
                  WHERE e.id = ?""", (eid,), one=True)
    att = db.q('SELECT * FROM attendance WHERE employee_id=? AND tanggal=?', (eid, tanggal), one=True)
    jd = db.jobdesk_untuk(eid)
    tsel = {t['jobdesk_id']: t for t in db.q(
        'SELECT * FROM daily_tasks WHERE employee_id=? AND tanggal=?', (eid, tanggal))}
    tasks = []
    for j in jd:
        t = tsel.get(j['id'])
        tasks.append({'jobdesk_id': j['id'], 'judul': j['judul'], 'kategori': j['kategori'],
                      'deskripsi': j['deskripsi'], 'selesai': (t or {}).get('selesai', 0),
                      'waktu_selesai': (t or {}).get('waktu_selesai')})
    selesai = sum(1 for t in tasks if t['selesai'])
    riwayat = db.q("""SELECT a.*, 
                        (SELECT id FROM attendance_photos p WHERE p.attendance_id=a.id AND p.jenis='checkin') AS foto_masuk,
                        (SELECT id FROM attendance_photos p WHERE p.attendance_id=a.id AND p.jenis='checkout') AS foto_pulang
                      FROM attendance a WHERE a.employee_id=? ORDER BY a.tanggal DESC LIMIT 14""", (eid,))
    for r in riwayat:
        r['status_tampil'] = db.status_absensi(r, set_)
    return ok({
        'karyawan': {'id': emp['id'], 'nama': emp['nama'], 'jabatan': emp['jabatan'], 'nik': emp['nik'],
                     'divisi': emp['divisi'] or '', 'foto_profil': emp['foto_profil'], 'tgl_masuk': emp['tgl_masuk']},
        'tanggal': tanggal, 'jam_server': db.now().strftime('%H:%M:%S'), 'settings': _set_dto(set_),
        'attendance': _att_dto(att, None, set_) if att else None,
        'status_hari_ini': db.status_absensi(att, set_),
        'tasks': tasks, 'task_selesai': selesai, 'task_total': len(tasks),
        'task_persen': round(selesai * 100 / len(tasks)) if tasks else 0,
        'riwayat': riwayat})


# ============================================================ LAPORAN + EXPORT
def _laporan_att(qs):
    sql = """SELECT a.tanggal, e.nama, e.nik, e.jabatan, d.nama AS divisi, a.checkin_at, a.checkout_at,
                    a.status, a.terlambat_menit, a.durasi_menit,
                    (SELECT COUNT(*) FROM attendance_photos p WHERE p.attendance_id=a.id AND p.jenis='checkin') AS f_masuk,
                    (SELECT COUNT(*) FROM attendance_photos p WHERE p.attendance_id=a.id AND p.jenis='checkout') AS f_pulang
             FROM attendance a JOIN employees e ON e.id = a.employee_id
             LEFT JOIN divisions d ON d.id = e.division_id WHERE 1=1"""
    args = []
    if qs.get('from'):
        sql += ' AND a.tanggal >= ?'
        args.append(qs['from'])
    if qs.get('to'):
        sql += ' AND a.tanggal <= ?'
        args.append(qs['to'])
    if qs.get('division_id'):
        sql += ' AND e.division_id = ?'
        args.append(int(qs['division_id']))
    if qs.get('employee_id'):
        sql += ' AND e.id = ?'
        args.append(int(qs['employee_id']))
    if qs.get('q'):
        sql += ' AND e.nama LIKE ?'
        args.append('%' + qs['q'] + '%')
    sql += ' ORDER BY a.tanggal DESC, e.nama'
    set_ = db.settings()
    out = []
    for r in db.q(sql, args):
        t = db.q("""SELECT SUM(selesai) AS s, COUNT(*) AS c FROM daily_tasks
                    WHERE employee_id = (SELECT id FROM employees WHERE nik = ?) AND tanggal = ?""",
                 (r['nik'], r['tanggal']), one=True) or {}
        target = None
        emp = db.q('SELECT id, division_id FROM employees WHERE nik = ?', (r['nik'],), one=True)
        if emp:
            target = len(db.jobdesk_untuk(emp['id']))
        out.append({**r,
                    'status_tampil': db.status_absensi(r, set_),
                    'durasi_jam': round((r['durasi_menit'] or 0) / 60, 2) if r['durasi_menit'] is not None else 0,
                    'task_selesai': (t or {}).get('s') or 0, 'task_target': target or 0,
                    'task_persen': round(((t or {}).get('s') or 0) * 100 / target) if target else 0,
                    'bukti_foto': ('lengkap' if (r['f_masuk'] and r['f_pulang']) else ('masuk' if r['f_masuk'] else 'tidak ada'))})
    return out


def _laporan_task(qs):
    sql = """SELECT t.tanggal, e.nama, e.nik, e.jabatan, d.nama AS divisi,
                    COUNT(t.id) AS tercatat, SUM(t.selesai) AS selesai,
                    GROUP_CONCAT(CASE WHEN t.selesai=1 THEN j.judul END, '; ') AS judul_selesai
             FROM daily_tasks t JOIN employees e ON e.id = t.employee_id
             JOIN jobdesks j ON j.id = t.jobdesk_id
             LEFT JOIN divisions d ON d.id = e.division_id WHERE 1=1"""
    args = []
    if qs.get('from'):
        sql += ' AND t.tanggal >= ?'
        args.append(qs['from'])
    if qs.get('to'):
        sql += ' AND t.tanggal <= ?'
        args.append(qs['to'])
    if qs.get('division_id'):
        sql += ' AND e.division_id = ?'
        args.append(int(qs['division_id']))
    if qs.get('employee_id'):
        sql += ' AND e.id = ?'
        args.append(int(qs['employee_id']))
    if qs.get('q'):
        sql += ' AND e.nama LIKE ?'
        args.append('%' + qs['q'] + '%')
    sql += ' GROUP BY t.tanggal, e.id ORDER BY t.tanggal DESC, e.nama'
    out = []
    for r in db.q(sql, args):
        emp = db.q('SELECT id FROM employees WHERE nik = ?', (r['nik'],), one=True)
        target = len(db.jobdesk_untuk(emp['id'])) if emp else 0
        out.append({**r, 'target': target, 'persen': round((r['selesai'] or 0) * 100 / target) if target else 0})
    return out


@route('GET', r'^/api/reports/attendance$', 'admin')
def api_rep_att(h, m, body, s):
    qs = h._query()
    data = _laporan_att(qs)
    return ok({'data': data, 'jumlah': len(data),
               'ringkasan': {
                   'hadir': sum(1 for d in data if d['status'] == 'Hadir'),
                   'terlambat': sum(1 for d in data if d['status'] == 'Terlambat'),
                   'total_jam': round(sum(d['durasi_jam'] for d in data), 2),
                   'rata_task': round(sum(d['task_persen'] for d in data) / len(data)) if data else 0}})


@route('GET', r'^/api/reports/tasks$', 'admin')
def api_rep_task(h, m, body, s):
    qs = h._query()
    data = _laporan_task(qs)
    return ok({'data': data, 'jumlah': len(data),
               'ringkasan': {'selesai': sum(d['selesai'] or 0 for d in data),
                             'rata_persen': round(sum(d['persen'] for d in data) / len(data)) if data else 0}})


@route('GET', r'^/api/export/xlsx$', 'admin')
def api_xlsx(h, m, body, s):
    qs = h._query()
    jenis = qs.get('jenis', 'kehadiran')
    if jenis == 'task':
        data = _laporan_task(qs)
        kolom = ['Tanggal', 'Nama', 'NIK', 'Jabatan', 'Divisi', 'Selesai', 'Target Jobdesk', 'Persen', 'Pekerjaan Selesai']
        baris = [[d['tanggal'], d['nama'], d['nik'], d['jabatan'], d['divisi'] or '', d['selesai'] or 0,
                  d['target'], d['persen'], d['judul_selesai'] or ''] for d in data]
        lebar = [12, 22, 12, 22, 14, 9, 14, 9, 60]
        nama_sheet = 'Laporan Task Harian'
    else:
        data = _laporan_att(qs)
        kolom = ['Tanggal', 'Nama', 'NIK', 'Jabatan', 'Divisi', 'Jam Masuk', 'Jam Pulang', 'Durasi (jam)',
                 'Terlambat (menit)', 'Status', 'Bukti Foto', 'Task Selesai', 'Target', 'Persen Task']
        baris = [[d['tanggal'], d['nama'], d['nik'], d['jabatan'], d['divisi'] or '',
                  (d['checkin_at'] or '')[11:], (d['checkout_at'] or '')[11:], d['durasi_jam'],
                  d['terlambat_menit'], d['status_tampil'], d['bukti_foto'], d['task_selesai'],
                  d['task_target'], d['task_persen']] for d in data]
        lebar = [12, 22, 12, 22, 14, 10, 10, 12, 14, 16, 12, 12, 8, 10]
        nama_sheet = 'Laporan Kehadiran'
    sheets = [{'nama': nama_sheet, 'kolom': [{'lebar': w} for w in lebar], 'baris': [kolom] + baris}]
    ring = qs.get('from', 'awal') + '_' + qs.get('to', db.today())
    path = os.path.join(db.DATA_DIR, 'export_%s_%s.xlsx' % (jenis, ring.replace('/', '-')))
    os.makedirs(db.DATA_DIR, exist_ok=True)
    report.write_xlsx(path, sheets)
    with open(path, 'rb') as f:
        isi = f.read()
    db.log(s['user_id'], 'export_xlsx', jenis)
    return Resp(200, isi, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@route('GET', r'^/api/export/pdf$', 'admin')
def api_pdf(h, m, body, s):
    qs = h._query()
    jenis = qs.get('jenis', 'kehadiran')
    set_ = db.settings()
    periode = 'Periode %s s/d %s' % (qs.get('from', 'awal'), qs.get('to', db.today()))
    if qs.get('division_id'):
        dv = db.q('SELECT nama FROM divisions WHERE id = ?', (int(qs['division_id']),), one=True)
        if dv:
            periode += '  |  Divisi: %s' % dv['nama']
    if jenis == 'task':
        data = _laporan_task(qs)
        kolom = ['Tanggal', 'Nama', 'Jabatan', 'Divisi', 'Selesai', 'Target', '%', 'Pekerjaan yang diselesaikan']
        baris = [[d['tanggal'], d['nama'], d['jabatan'], d['divisi'] or '', d['selesai'] or 0, d['target'],
                  '%d%%' % d['persen'], d['judul_selesai'] or '-'] for d in data]
        lebar = [58, 110, 110, 78, 40, 40, 30, 296]
        judul = 'LAPORAN TASK HARIAN'
    else:
        data = _laporan_att(qs)
        kolom = ['Tanggal', 'Nama', 'Jabatan', 'Divisi', 'Masuk', 'Pulang', 'Durasi', 'Telat', 'Status', 'Foto', 'Task %']
        baris = [[d['tanggal'], d['nama'], d['jabatan'], d['divisi'] or '', (d['checkin_at'] or '')[11:16],
                  (d['checkout_at'] or '')[11:16], '%.2f jam' % d['durasi_jam'], '%d mnt' % d['terlambat_menit'],
                  d['status_tampil'], d['bukti_foto'], '%d%%' % d['task_persen']] for d in data]
        lebar = [58, 110, 110, 78, 42, 42, 48, 40, 92, 62, 40]
        judul = 'LAPORAN KEHADIRAN'
    path = os.path.join(db.DATA_DIR, 'laporan_%s_%s.pdf' % (jenis, db.today()))
    os.makedirs(db.DATA_DIR, exist_ok=True)
    report.write_pdf(path, judul, kolom, baris, lebar, landscape=True,
                     subjudul='%s  |  %s' % (set_['nama_instansi'], periode))
    with open(path, 'rb') as f:
        isi = f.read()
    db.log(s['user_id'], 'export_pdf', jenis)
    return Resp(200, isi, 'application/pdf')


# ============================================================ PENGATURAN & PROFIL
@route('PUT', r'^/api/settings$', 'admin')
def api_set_put(h, m, body, s):
    cek(db.settings(), 500, 'Pengaturan belum terinisialisasi.')
    pola = re.compile(r'^([01]\d|2[0-3]):[0-5]\d$')
    jm = str(body.get('jam_masuk', '')).strip()
    jp = str(body.get('jam_pulang', '')).strip()
    cek(pola.match(jm), 400, 'Jam masuk tidak valid (format HH:MM).')
    cek(pola.match(jp), 400, 'Jam pulang tidak valid (format HH:MM).')
    tol = int(body.get('toleransi_menit') or 0)
    cek(0 <= tol <= 240, 400, 'Toleransi 0-240 menit.')
    hari = ','.join(str(d) for d in body.get('hari_kerja', [1, 2, 3, 4, 5]) if str(d).isdigit())
    cek(hari != '', 400, 'Pilih minimal satu hari kerja.')
    db.x("""UPDATE work_settings SET nama_instansi=?, jam_masuk=?, jam_pulang=?, toleransi_menit=?,
            hari_kerja=?, zona_waktu=?, wajib_foto=?, updated_at=? WHERE id=1""",
         (str(body.get('nama_instansi', '')).strip() or 'Perusahaan', jm, jp, tol, hari,
          str(body.get('zona_waktu', 'WIB')).strip()[:10], 1 if body.get('wajib_foto', 1) else 0, db.now_iso()))
    db.log(s['user_id'], 'setting_ubah', '%s-%s tol %s' % (jm, jp, tol))
    return ok({'settings': _set_dto(db.settings())})


@route('GET', r'^/api/log$', 'admin')
def api_log(h, m, body, s):
    lim = min(int(h._query().get('limit') or 100), 500)
    return ok({'data': db.q("""SELECT l.*, u.username, u.role FROM activity_log l
                              LEFT JOIN users u ON u.id = l.user_id ORDER BY l.id DESC LIMIT ?""", (lim,))})


@route('GET', r'^/api/profil$')
def api_profil(h, m, body, s):
    u = db.q('SELECT * FROM users WHERE id = ?', (s['user_id'],), one=True)
    emp = db.q('SELECT * FROM employees WHERE id = ?', (u['employee_id'],), one=True) if u['employee_id'] else None
    return ok({'user': {'id': u['id'], 'username': u['username'], 'email': u['email'], 'role': u['role'],
                        'last_login': u['last_login']},
               'karyawan': ({k: emp[k] for k in ('id', 'nama', 'nik', 'jabatan', 'telepon', 'email', 'foto_profil', 'tgl_masuk')} if emp else None)})


@route('PUT', r'^/api/profil$')
def api_profil_put(h, m, body, s):
    uid = s['user_id']
    if body.get('nama') and s['employee_id']:
        nama = str(body['nama']).strip()
        cek(len(nama) >= 2, 400, 'Nama minimal 2 karakter.')
        db.x('UPDATE employees SET nama=?, telepon=?, email=? WHERE id=?',
             (nama, str(body.get('telepon', '')).strip(), str(body.get('email', '')).strip(), s['employee_id']))
    if body.get('email'):
        db.x('UPDATE users SET email = ? WHERE id = ?', (str(body['email']).strip(), uid))
    if body.get('foto_profil'):
        cek(s['employee_id'], 400, 'Akun admin tidak punya foto profil karyawan.')
        data_url = str(body['foto_profil'])
        cek(data_url.startswith('data:image/'), 400, 'Format foto profil tidak valid.')
        try:
            raw = base64.b64decode(data_url.split(',', 1)[1], validate=True)
        except (ValueError, binascii.Error):
            raise ApiError(400, 'Data foto profil rusak.')
        cek(len(raw) <= 2 * 1024 * 1024, 413, 'Foto profil maks 2 MB.')
        sub = os.path.join(FOTO_DIR, 'profil')
        os.makedirs(sub, exist_ok=True)
        nama = 'profil_%d_%s.jpg' % (s['employee_id'], secrets.token_hex(4))
        path = os.path.join(sub, nama)
        with open(path, 'wb') as f:
            f.write(raw)
        db.x('UPDATE employees SET foto_profil = ? WHERE id = ?', (path, s['employee_id']))
    if body.get('username'):
        baru = re.sub(r'[^a-z0-9._]', '', str(body['username']).strip().lower())
        cek(len(baru) >= 3, 400, 'Username minimal 3 karakter.')
        cek(not db.q('SELECT id FROM users WHERE lower(username)=? AND id<>?', (baru, uid), one=True), 409, 'Username sudah dipakai.')
        db.x('UPDATE users SET username=? WHERE id=?', (baru, uid))
    db.log(uid, 'profil_ubah')
    return ok()


@route('POST', r'^/api/profil/password$')
def api_profil_pass(h, m, body, s):
    lama = str(body.get('lama', ''))
    baru = str(body.get('baru', ''))
    cek(len(baru) >= 6, 400, 'Password baru minimal 6 karakter.')
    u = db.q('SELECT * FROM users WHERE id = ?', (s['user_id'],), one=True)
    cek(db.verify_password(lama, u['password_hash'], u['salt']), 400, 'Password lama tidak sesuai.')
    hsh, salt = db.hash_password(baru)
    db.x('UPDATE users SET password_hash=?, salt=? WHERE id=?', (hsh, salt, u['id']))
    db.x('DELETE FROM sessions WHERE user_id = ? AND token <> ?', (u['id'], h._cookies().get('sid')))
    db.log(u['id'], 'password_ganti')
    return ok()


@route('GET', r'^/api/foto-profil/(?P<id>\d+)$')
def api_foto_profil(h, m, body, s):
    eid = int(m.group('id'))
    emp = db.q('SELECT foto_profil, nama FROM employees WHERE id = ?', (eid,), one=True)
    cek(emp is not None, 404, 'Karyawan tidak ditemukan.')
    if emp['foto_profil'] and os.path.isfile(emp['foto_profil']):
        with open(emp['foto_profil'], 'rb') as f:
            return Resp(200, f.read(), 'image/jpeg')
    # avatar inisial (SVG) bila belum ada foto
    inisial = ''.join(w[0] for w in emp['nama'].split()[:2]).upper()
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128"><rect width="128" height="128" rx="64" fill="#1e293b"/>'
           '<text x="64" y="82" font-family="Arial" font-size="48" fill="#93c5fd" text-anchor="middle">%s</text></svg>' % inisial)
    return Resp(200, svg.encode('utf-8'), 'image/svg+xml')


# ============================================================ MAIN
def main():
    ap = argparse.ArgumentParser(description='Nufatur Absensi - Server Absensi Karyawan & Task Management')
    ap.add_argument('--port', type=int, default=8080)
    ap.add_argument('--host', default='0.0.0.0', help='0.0.0.0 = bisa diakses dari HP di jaringan yang sama')
    ap.add_argument('--reset-db', action='store_true', help='Hapus database lalu buat ulang data contoh')
    a = ap.parse_args()

    if a.reset_db:
        for p in (db.DB_PATH, db.DB_PATH + '-wal', db.DB_PATH + '-shm'):
            if os.path.exists(p):
                os.remove(p)
    db.init_db()

    ip_lokal = '127.0.0.1'
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip_lokal = s.getsockname()[0]
        s.close()
    except OSError:
        pass

    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    srv.daemon_threads = True
    print('=' * 66)
    print('  NUFATUR ABSENSI - ABSENSI KARYAWAN & TASK MANAGEMENT')
    print('=' * 66)
    print('  Server lokal  : http://127.0.0.1:%d' % a.port)
    print('  Dari HP/LAN   : http://%s:%d   (satu jaringan Wi-Fi)' % (ip_lokal, a.port))
    print('  Database      : %s' % db.DB_PATH)
    print('  Foto absensi  : %s' % FOTO_DIR)
    print('  Akun awal     : %s' % os.path.join(BASE, 'AKUN-AWAL.txt'))
    print('  Stop server   : Ctrl + C')
    print('=' * 66)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\nServer dihentikan.')
        srv.shutdown()


if __name__ == '__main__':
    main()
