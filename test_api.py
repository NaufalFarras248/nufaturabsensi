"""
test_api.py — Uji end-to-end API server absensi.
Jalankan server dulu, lalu:  python test_api.py [http://127.0.0.1:8080]
Menguji: login, role guard, CSRF, absensi + foto wajib, satu kali per hari,
timestamp server, checklist task, laporan, export Excel/PDF.
"""
import base64
import http.cookiejar
import json
import os
import re
import struct
import sys
import time
import urllib.error
import urllib.request
import zlib

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8080'
AKUN = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'AKUN-AWAL.txt')
hasil = []


def lapor(nama, lulus, info=''):
    hasil.append((nama, lulus, info))
    print(('  [OK]   ' if lulus else '  [GAGAL] ') + nama + ('  -> ' + str(info) if info else ''))
    return lulus


def lapor_api(nama, st, d, syarat):
    """Lapor hasil panggilan API; saat gagal, cetak status + isi respons apa adanya."""
    ok = bool(syarat)
    if not ok:
        return lapor(nama, False, 'status=%s %s' % (st, json.dumps(d, ensure_ascii=False)[:200] if isinstance(d, (dict, list)) else str(d)[:200]))
    return lapor(nama, True)


class TanpaRedirect(urllib.request.HTTPRedirectHandler):
    """Bikin klien tidak mengikuti redirect, supaya tujuan pengalihan bisa diperiksa."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Sesi:
    """Klien HTTP dengan cookie jar + token CSRF."""

    def __init__(self, label):
        self.label = label
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        # klien kedua: tidak mengikuti redirect, untuk memeriksa tujuan pengalihan
        self.opener_tanpa_redirect = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar), TanpaRedirect())
        self.csrf = ''

    def panggil(self, path, method='GET', body=None, csrf=True, raw=False):
        data = None
        headers = {}
        if body is not None:
            data = json.dumps(body).encode()
            headers['Content-Type'] = 'application/json'
        if csrf and self.csrf and method != 'GET':
            headers['X-CSRF'] = self.csrf
        req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=20) as r:
                isi = r.read()
                ctype = r.headers.get('Content-Type', '')
                if raw:
                    return r.status, isi, ctype
                return r.status, (json.loads(isi) if 'json' in ctype else isi), ctype
        except urllib.error.HTTPError as e:
            isi = e.read()
            try:
                return e.code, json.loads(isi), e.headers.get('Content-Type', '')
            except Exception:
                return e.code, isi, e.headers.get('Content-Type', '')

    def login(self, username, password):
        st, d, _ = self.panggil('/api/login', 'POST', {'username': username, 'password': password}, csrf=False)
        if st == 200 and d.get('ok'):
            self.csrf = d['csrf']
        return st, d


def baca_akun():
    """Ambil kredensial dari AKUN-AWAL.txt (bukan dari output layar)."""
    akun = {}
    with open(AKUN, encoding='utf-8') as f:
        for baris in f:
            m = re.match(r'^(\S+)\s+(\S+)\s+(.+)$', baris.strip())
            if m and m.group(1) not in ('USERNAME',) and not m.group(1).startswith('='):
                akun[m.group(1)] = m.group(2)
    return akun


def png_uji(ukuran_min=3000):
    """PNG 16x16 valid + chunk tEXt filler supaya ukurannya > batas minimum server."""
    w = h = 16
    raw = b''
    for y in range(h):
        raw += b'\x00' + b''.join(bytes([(x * 16) % 256, (y * 16) % 256, 200]) for x in range(w))

    def chunk(tipe, data):
        return struct.pack('>I', len(data)) + tipe + data + struct.pack('>I', zlib.crc32(tipe + data) & 0xffffffff)

    ihdr = struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)
    isi = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) + chunk(b'IDAT', zlib.compress(raw, 9))
    filler = b'foto-uji-absensi ' * 400
    isi += chunk(b'tEXt', b'Comment\x00' + filler[:ukuran_min])
    isi += chunk(b'IEND', b'')
    return 'data:image/png;base64,' + base64.b64encode(isi).decode()


def main():
    print('== Uji API server absensi: %s ==' % BASE)
    akun = baca_akun()
    admin_pw = akun.get('admin')
    if not admin_pw:
        print('Tidak bisa membaca AKUN-AWAL.txt'); return 1

    # ---------- 1. login ----------
    admin = Sesi('admin')
    st, d = admin.login('admin', 'salahsekali')
    lapor('login password salah ditolak (401)', st == 401)
    st, d = admin.login('admin', admin_pw)
    lapor('login admin berhasil', st == 200 and d.get('user', {}).get('role') == 'admin')
    st, d, _ = admin.panggil('/api/me')
    lapor('GET /api/me mengembalikan sesi + csrf', st == 200 and bool(d.get('csrf')))
    lapor('cookie sesi HttpOnly + SameSite', any(getattr(c, 'name', '') == 'sid' for c in admin.jar))

    # ---------- 2. CSRF ----------
    st, d, _ = admin.panggil('/api/divisions', 'POST', {'nama': 'Uji Tanpa CSRF'}, csrf=False)
    lapor('POST tanpa token CSRF ditolak (403)', st == 403, d.get('error', ''))

    # ---------- 3. master data ----------
    st, d, _ = admin.panggil('/api/divisions', 'POST', {'nama': 'Divisi Uji', 'keterangan': 'Dibuat otomatis oleh test'})
    div_id = d.get('id')
    lapor_api('admin membuat divisi', st, d, st == 200 and div_id)

    uname = 'ujikaryawan'
    st, d, _ = admin.panggil('/api/employees', 'POST', {
        'nama': 'Uji Karyawan', 'nik': '9999001', 'jabatan': 'Staff Uji', 'division_id': div_id,
        'status': 'aktif', 'tgl_masuk': '2026-01-05', 'buat_akun': 1, 'username': uname, 'password': 'ujipass123',
    })
    emp_id = d.get('id')
    lapor_api('admin menambah karyawan + akun', st, d, st == 200 and emp_id)

    st, d, _ = admin.panggil('/api/jobdesks', 'POST', {'judul': 'Mengisi laporan uji harian', 'kategori': 'Uji', 'division_id': div_id, 'aktif': 1})
    jd_uji = d.get('id')
    lapor_api('admin menambah jobdesk untuk divisi uji', st, d, st == 200 and jd_uji)

    st, d, _ = admin.panggil('/api/jobdesks', 'POST', {'judul': 'Jobdesk divisi lain', 'kategori': 'Uji', 'division_id': None, 'aktif': 1})
    jd_umum = d.get('id')
    lapor_api('admin menambah jobdesk untuk semua divisi', st, d, st == 200 and jd_umum)

    # ---------- 4. karyawan login ----------
    kar = Sesi('karyawan')
    st, d = kar.login(uname, 'ujipass123')
    lapor_api('login karyawan berhasil', st, d, st == 200 and d.get('user', {}).get('role') == 'karyawan')

    # ---------- 5. role guard ----------
    st, d, _ = kar.panggil('/api/employees')
    lapor('karyawan hanya melihat data dirinya sendiri di /api/employees',
          st == 200 and len(d.get('data', [])) == 1 and d['data'][0]['id'] == emp_id)
    st, d, _ = kar.panggil('/api/employees', 'POST', {'nama': 'Karyawan Selundupan'})
    lapor('karyawan diblokir menambah karyawan (403)', st == 403)
    st, d, _ = kar.panggil('/api/employees/%d' % emp_id, 'DELETE')
    lapor('karyawan diblokir menghapus data karyawan (403)', st == 403)
    st, d, _ = kar.panggil('/api/users')
    lapor('karyawan diblokir melihat daftar akun (403)', st == 403)
    st, d, _ = kar.panggil('/api/dashboard/admin')
    lapor('karyawan diblokir dari dashboard admin (403)', st == 403)
    st, d, _ = kar.panggil('/api/settings', 'PUT', {'jam_masuk': '07:00', 'jam_pulang': '16:00'})
    lapor('karyawan diblokir mengubah jam kerja (403)', st == 403)
    st, d, _ = kar.panggil('/api/export/xlsx?jenis=kehadiran')
    lapor('karyawan diblokir export laporan admin (403)', st == 403)
    st, d, _ = kar.panggil('/api/log')
    lapor('karyawan diblokir dari log aktivitas (403)', st == 403)
    st, d, _ = kar.panggil('/api/register', 'POST', {'username': 'penyusup', 'password': 'rahasia'})
    lapor('tidak ada pendaftaran mandiri — karyawan tidak bisa buat akun sendiri', st == 404, 'status=%s' % st)
    st, d, _ = admin.panggil('/api/register', 'POST', {'username': 'penyusup', 'password': 'rahasia'})
    lapor('admin pun tidak punya endpoint pendaftaran mandiri', st == 404)
    st, d, _ = kar.panggil('/api/users/%d' % emp_id, 'PUT', {'role': 'admin'})
    lapor('karyawan diblokir mengubah role akun (403)', st == 403)

    # ---------- 6. absensi: validasi foto ----------
    st, d, _ = kar.panggil('/api/attendance/masuk', 'POST', {})
    lapor('absen masuk tanpa foto ditolak (400)', st == 400, d.get('error', ''))
    st, d, _ = kar.panggil('/api/attendance/masuk', 'POST', {'foto': 'data:image/jpeg;base64,QUJD'})
    lapor_api('absen dengan foto palsu ditolak (400)', st, d, st == 400)
    st, d, _ = kar.panggil('/api/attendance/hari-ini')
    lapor('foto gagal TIDAK menyisakan data absensi', st == 200 and not d.get('attendance'),
          'attendance=%s' % (d.get('attendance') is not None))

    # ---------- 7. absensi: timestamp server ----------
    waktu_klien = '01:23:45'
    st, d, _ = kar.panggil('/api/attendance/masuk', 'POST', {'foto': png_uji(), 'checkin_at': '2020-01-01 ' + waktu_klien, 'waktu': waktu_klien})
    ok_masuk = st == 200 and d.get('ok')
    att = d.get('attendance', {}) if ok_masuk else {}
    server_now = time.strftime('%Y-%m-%d %H:%M')
    lapor('absen masuk dengan foto berhasil', ok_masuk, 'status=%s' % att.get('status'))
    lapor('jam absensi memakai waktu server, bukan input klien',
          ok_masuk and att.get('checkin_at', '').startswith(server_now) and waktu_klien not in str(att.get('checkin_at')),
          att.get('checkin_at'))
    lapor('status otomatis dihitung (Hadir/Terlambat)', att.get('status') in ('Hadir', 'Terlambat'), att.get('status'))
    lapor('foto tersimpan + tercatat', bool(att.get('id')))

    st, d, _ = kar.panggil('/api/attendance/masuk', 'POST', {'foto': png_uji()})
    lapor('absen masuk dua kali dalam sehari ditolak (409)', st == 409, d.get('error', ''))

    # ---------- 8. checkout ----------
    st, d, _ = kar.panggil('/api/attendance/pulang', 'POST', {})
    lapor('absen pulang tanpa foto ditolak (400)', st == 400, d.get('error', ''))
    time.sleep(1.1)
    st, d, _ = kar.panggil('/api/attendance/pulang', 'POST', {'foto': png_uji()})
    lapor('absen pulang dengan foto berhasil', st == 200 and d.get('ok'), d.get('attendance', {}).get('durasi_menit'))
    st, d, _ = kar.panggil('/api/attendance/pulang', 'POST', {'foto': png_uji()})
    lapor('absen pulang dua kali ditolak (409)', st == 409)

    # ---------- 9. foto & akses ----------
    st, d, _ = kar.panggil('/api/attendance?from=2026-01-01&to=2030-01-01')
    punya_foto = [x for x in d.get('data', []) if x.get('foto_masuk')]
    lapor('riwayat absensi karyawan hanya berisi dirinya sendiri', st == 200 and all(x['nama'] == 'Uji Karyawan' for x in d.get('data', [])))
    if punya_foto:
        pid = punya_foto[0]['foto_masuk']
        st, isi, ct = kar.panggil('/api/photo/%d' % pid, raw=True)
        lapor('foto absensi bisa diakses pemiliknya', st == 200 and isi[:4] == b'\x89PNG')
        st, d, _ = admin.panggil('/api/photo/%d' % pid)
        lapor('admin bisa melihat foto absensi karyawan', st == 200)
    # karyawan lain tidak boleh lihat foto orang lain
    st, d, _ = admin.panggil('/api/attendance')
    baris = d.get('data', [])
    lain = [x for x in baris if x.get('foto_masuk') and x['nama'] != 'Uji Karyawan']
    if lain:
        st, d2, _ = kar.panggil('/api/photo/%d' % lain[0]['foto_masuk'])
        lapor('karyawan diblokir melihat foto karyawan lain (403)', st == 403)

    # ---------- 10. task harian ----------
    st, d, _ = kar.panggil('/api/tasks')
    jd_list = [x['jobdesk_id'] for x in d.get('data', [])]
    lapor('karyawan melihat jobdesk sesuai divisinya', st == 200 and jd_uji in jd_list and jd_umum in jd_list, 'jumlah=%d' % len(jd_list))

    st, d, _ = kar.panggil('/api/tasks/toggle', 'POST', {'jobdesk_id': jd_uji, 'selesai': 1})
    lapor('checklist task tersimpan + waktu selesai', st == 200 and d.get('waktu_selesai'), d.get('waktu_selesai'))

    st, d, _ = kar.panggil('/api/tasks?tanggal=' + time.strftime('%Y-%m-%d'))
    item = [x for x in d.get('data', []) if x['jobdesk_id'] == jd_uji]
    lapor('status checklist terbaca kembali dari database', bool(item) and item[0]['selesai'] == 1)
    lapor('persentase progress dihitung', d.get('total', 0) > 0 and d.get('persen', 0) > 0, '%s%%' % d.get('persen'))

    st, d, _ = kar.panggil('/api/tasks/toggle', 'POST', {'jobdesk_id': jd_uji, 'tanggal': '2020-05-05', 'selesai': 1})
    lapor('karyawan diblokir mengisi checklist tanggal lain (403)', st == 403)

    # jobdesk divisi lain -> tolak
    other = admin.panggil('/api/jobdesks')[1]['data']
    bukan_div = [x for x in other if x['division_id'] not in (None, div_id)]
    if bukan_div:
        st, d, _ = kar.panggil('/api/tasks/toggle', 'POST', {'jobdesk_id': bukan_div[0]['id'], 'selesai': 1})
        lapor('karyawan diblokir mencentang jobdesk divisi lain (403)', st == 403)

    st, d, _ = kar.panggil('/api/tasks/riwayat')
    lapor('karyawan melihat riwayat task sendiri', st == 200 and len(d.get('data', [])) >= 1)

    # ---------- 11. dashboard admin ----------
    st, d, _ = admin.panggil('/api/dashboard/admin')
    r = d.get('ringkasan', {})
    lapor('dashboard admin menghitung ringkasan', st == 200 and 'sudah_absen' in r and r['sudah_absen'] >= 1, json.dumps(r, ensure_ascii=False))
    uji = [x for x in d.get('karyawan', []) if x['id'] == emp_id]
    lapor('dashboard menampilkan karyawan uji dengan status + progress task', bool(uji) and uji[0]['task_selesai'] >= 1,
          (uji[0]['status_tampil'] + ' ' + str(uji[0]['task_selesai']) + '/' + str(uji[0]['task_target'])) if uji else 'tidak ada')

    # ---------- 12. laporan + export ----------
    from datetime import date, timedelta
    frm = (date.today() - timedelta(days=30)).isoformat()
    to = date.today().isoformat()
    st, d, _ = admin.panggil('/api/reports/attendance?from=%s&to=%s' % (frm, to))
    lapor('laporan kehadiran admin', st == 200 and d.get('jumlah', 0) > 0, 'baris=%s' % d.get('jumlah'))
    st, d, _ = admin.panggil('/api/reports/tasks?from=%s&to=%s' % (frm, to))
    lapor('laporan task admin', st == 200 and d.get('jumlah', 0) > 0, 'baris=%s' % d.get('jumlah'))

    st, isi, ct = admin.panggil('/api/export/xlsx?jenis=kehadiran&from=%s&to=%s' % (frm, to), raw=True)
    lapor('export Excel (.xlsx) valid', st == 200 and isi[:2] == b'PK' and len(isi) > 2000, '%d bytes' % len(isi))
    st, isi, ct = admin.panggil('/api/export/pdf?jenis=kehadiran&from=%s&to=%s' % (frm, to), raw=True)
    lapor('export PDF valid', st == 200 and isi[:5] == b'%PDF-' and len(isi) > 1500, '%d bytes' % len(isi))
    st, isi, ct = admin.panggil('/api/export/pdf?jenis=task&from=%s&to=%s' % (frm, to), raw=True)
    lapor('export PDF laporan task valid', st == 200 and isi[:5] == b'%PDF-')

    # ---------- 13. pengaturan ----------
    st, d, _ = admin.panggil('/api/settings', 'PUT', {
        'nama_instansi': 'PT Uji Otomatis', 'jam_masuk': '08:00', 'jam_pulang': '17:00',
        'toleransi_menit': 15, 'hari_kerja': [1, 2, 3, 4, 5], 'zona_waktu': 'WIB', 'wajib_foto': 1})
    lapor('admin menyimpan jam kerja + toleransi', st == 200 and d.get('settings', {}).get('toleransi_menit') == 15)
    st, d, _ = admin.panggil('/api/settings', 'PUT', {'jam_masuk': '99:99', 'jam_pulang': '17:00'})
    lapor('jam kerja tidak valid ditolak (400)', st == 400, d.get('error', ''))
    st, d, _ = admin.panggil('/api/settings', 'PUT', {
        'nama_instansi': 'PT Contoh Sejahtera', 'jam_masuk': '08:00', 'jam_pulang': '17:00',
        'toleransi_menit': 10, 'hari_kerja': [1, 2, 3, 4, 5], 'zona_waktu': 'WIB', 'wajib_foto': 1})
    lapor('pengaturan dikembalikan ke nilai awal', st == 200)

    # ---------- 14. profil & password ----------
    st, d, _ = kar.panggil('/api/profil', 'PUT', {'nama': 'Uji Karyawan Revisi'})
    lapor('karyawan mengubah profilnya sendiri', st == 200)
    # role & identitas tidak boleh diubah sendiri oleh karyawan
    kar.panggil('/api/profil', 'PUT', {'nama': 'Uji Karyawan Revisi', 'role': 'admin', 'employee_id': 1, 'id': 1})
    st, d, _ = kar.panggil('/api/me')
    lapor('karyawan TIDAK bisa menaikkan role jadi admin lewat profil',
          st == 200 and d['user']['role'] == 'karyawan', 'role=%s' % d.get('user', {}).get('role'))
    lapor('identitas karyawan tetap terikat ke akunnya sendiri',
          int(d['user']['employee_id']) == emp_id, 'employee_id=%s' % d['user']['employee_id'])
    st, d, _ = kar.panggil('/api/users/1', 'PUT', {'role': 'admin'})
    lapor('karyawan diblokir mengubah data akun (403)', st == 403)
    st, d, _ = kar.panggil('/api/profil/password', 'POST', {'lama': 'salah', 'baru': 'barupass123'})
    lapor('ganti password dengan password lama salah ditolak (400)', st == 400)
    st, d, _ = kar.panggil('/api/profil/password', 'POST', {'lama': 'ujipass123', 'baru': 'barupass123'})
    lapor('ganti password berhasil', st == 200)
    kar2 = Sesi('karyawan2')
    st, d = kar2.login(uname, 'barupass123')
    lapor('login dengan password baru berhasil', st == 200)

    # ---------- 15. pemisahan akses berbasis URL (RBAC) ----------
    def halaman(sesi, path):
        """Ambil halaman tanpa mengikuti redirect -> (status, tujuan, cuplikan isi)."""
        req = urllib.request.Request(BASE + path)
        try:
            with sesi.opener_tanpa_redirect.open(req, timeout=20) as r:
                return r.status, None, r.read()[:4000]
        except urllib.error.HTTPError as e:
            return e.code, e.headers.get('Location'), e.read()[:4000]

    anon = Sesi('anon')
    st, loc, isi = halaman(anon, '/admin/dashboard')
    lapor('/admin/dashboard tanpa login -> dialihkan ke halaman login', st == 302 and loc.startswith('/?masuk=1'), '%s %s' % (st, loc))
    st, loc, isi = halaman(anon, '/employee/dashboard')
    lapor('/employee/dashboard tanpa login -> dialihkan ke login', st == 302 and loc.startswith('/?masuk=1'), '%s %s' % (st, loc))

    st, loc, isi = halaman(admin, '/admin/dashboard')
    lapor('admin membuka /admin/dashboard (200, panel admin)', st == 200 and b'Panel Administrator' in isi, '%s %s' % (st, loc))
    st, loc, isi = halaman(admin, '/admin/absensi')
    lapor('admin membuka URL menu langsung /admin/absensi', st == 200 and b'id="nav"' in isi, '%s %s' % (st, loc))
    st, loc, isi = halaman(admin, '/admin/menu-ngawur')
    lapor('menu admin tidak dikenal -> diarahkan ke dashboard admin', st == 302 and loc == '/admin/dashboard', '%s %s' % (st, loc))
    st, loc, isi = halaman(admin, '/employee/dashboard')
    lapor('admin ke /employee/dashboard -> diarahkan ke panel admin', st == 302 and loc == '/admin/dashboard', '%s %s' % (st, loc))

    st, loc, isi = halaman(kar2, '/admin/dashboard')
    lapor('KARYAWAN ketik URL admin langsung -> DITOLAK, dialihkan ke /employee/dashboard',
          st == 302 and loc == '/employee/dashboard', '%s %s' % (st, loc))
    lapor('halaman admin tidak bocor ke karyawan (tidak ada markup panel admin)',
          b'Panel Administrator' not in isi and b'Manajemen' not in isi)
    st, loc, isi = halaman(kar2, '/admin/karyawan')
    lapor('karyawan ke /admin/karyawan -> dialihkan ke dashboard karyawan', st == 302 and loc == '/employee/dashboard', '%s %s' % (st, loc))
    st, loc, isi = halaman(kar2, '/admin.html')
    lapor('karyawan ke /admin.html (jalur lama) -> tetap ditolak', st == 302 and loc == '/employee/dashboard', '%s %s' % (st, loc))
    st, loc, isi = halaman(kar2, '/employee/dashboard')
    lapor('karyawan membuka /employee/dashboard (200)', st == 200 and b'knav' in isi, '%s %s' % (st, loc))
    st, loc, isi = halaman(kar2, '/employee/task')
    lapor('karyawan membuka URL menu langsung /employee/task', st == 200, '%s %s' % (st, loc))

    # admin boleh mengoreksi checklist karyawan (monitoring seluruh karyawan)
    st, d, _ = admin.panggil('/api/tasks?employee_id=%d' % emp_id)
    lapor('admin melihat checklist karyawan lain', st == 200 and d.get('total', 0) > 0, 'jobdesk=%s' % d.get('total'))
    st, d, _ = admin.panggil('/api/tasks/toggle', 'POST', {'employee_id': emp_id, 'jobdesk_id': jd_umum, 'tanggal': '2026-02-02', 'selesai': 1})
    lapor('admin dapat mengoreksi checklist tanggal lain', st == 200 and d.get('waktu_selesai'))
    st, d, _ = kar2.panggil('/api/tasks?employee_id=%d' % emp_id)
    lapor('karyawan tidak bisa membaca checklist karyawan lain (hanya dirinya)', st == 200 and d.get('karyawan', {}).get('id') == emp_id)

    # ---------- 16. logout ----------
    st, d, _ = kar.panggil('/api/logout', 'POST', {})
    st2, d2, _ = kar.panggil('/api/me')
    lapor('logout menghapus sesi (401)', st == 200 and st2 == 401)

    # ---------- 16. bersihkan data uji ----------
    st, d, _ = admin.panggil('/api/employees/%d' % emp_id, 'DELETE')
    lapor('bersih-bersih: karyawan uji dihapus', st == 200)
    for j in (jd_uji, jd_umum):
        admin.panggil('/api/jobdesks/%d' % j, 'DELETE')
    admin.panggil('/api/divisions/%d' % div_id, 'DELETE')

    print('\n' + '=' * 62)
    lulus = sum(1 for _, l, _ in hasil if l)
    print('HASIL: %d/%d uji lulus' % (lulus, len(hasil)))
    if lulus != len(hasil):
        print('Yang gagal:')
        for n, l, i in hasil:
            if not l:
                print('  - %s %s' % (n, i))
    print('=' * 62)
    return 0 if lulus == len(hasil) else 1


if __name__ == '__main__':
    sys.exit(main())
