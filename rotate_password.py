#!/usr/bin/env python3
"""Rotasi password semua akun absensi + tulis ke file lokal (tidak pernah ke stdout)."""
import os
import secrets
import sqlite3
import string
import sys
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, 'data', 'app.db')
OUT = os.path.join(BASE, 'AKUN-BARU.txt')

sys.path.insert(0, BASE)
import db as dbmod  # noqa: E402

ALPHABET = string.ascii_letters + string.digits


def gen(n=12):
    return ''.join(secrets.choice(ALPHABET) for _ in range(n))


con = sqlite3.connect(DB)
rows = con.execute(
    'SELECT u.id, u.username, u.role, e.nama FROM users u '
    'LEFT JOIN employees e ON e.id = u.employee_id ORDER BY u.role, u.username'
).fetchall()

hasil = []
for uid, username, role, nama in rows:
    pw = gen()
    h, salt = dbmod.hash_password(pw)
    con.execute('UPDATE users SET password_hash=?, salt=? WHERE id=?', (h, salt, uid))
    hasil.append((username, role, nama or '-', pw))
# semua sesi lama diputus
n_sesi = con.execute('SELECT COUNT(*) FROM sessions').fetchone()[0]
con.execute('DELETE FROM sessions')
con.commit()
con.close()

with open(OUT, 'w', encoding='utf-8') as f:
    f.write('AKUN BARU APLIKASI ABSENSI KARYAWAN\n')
    f.write('Diganti: %s\n' % datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    f.write('Semua password default lama sudah TIDAK berlaku.\n')
    f.write('=' * 62 + '\n')
    f.write('%-12s %-10s %-20s %s\n' % ('USERNAME', 'ROLE', 'NAMA', 'PASSWORD'))
    f.write('-' * 62 + '\n')
    for u, r, n, p in hasil:
        f.write('%-12s %-10s %-20s %s\n' % (u, r, n[:20], p))
    f.write('=' * 62 + '\n')
    f.write('Simpan file ini, lalu hapus setelah dicatat.\n')

print('akun dirotasi : %d' % len(hasil))
print('sesi diputus  : %d' % n_sesi)
print('file          : %s' % OUT)
print('panjang pw    : %d' % len(hasil[0][3]) if hasil else '')
print('username      : %s' % ', '.join(u for u, _, _, _ in hasil))
