/* ============================================================
   karyawan.js — Dashboard karyawan
   Menu: Absen (dashboard), Task Harian, Riwayat, Profil.
   ============================================================ */
'use strict';

const NAV = [
  { id: 'dash', label: 'Absen', icon: 'clock', path: 'dashboard' },
  { id: 'task', label: 'Task Harian', icon: 'checklist', path: 'task' },
  { id: 'riwayat', label: 'Riwayat', icon: 'report', path: 'riwayat' },
  { id: 'profil', label: 'Profil', icon: 'user', path: 'profil' },
];

/** Menu aktif dibaca dari URL: /employee/<path>. */
function navDariPath() {
  const s = location.pathname.split('/').filter(Boolean);
  if (!['employee', 'karyawan'].includes(s[0])) return 'dash';
  const n = NAV.find(x => x.path === s[1]);
  return n ? n.id : 'dash';
}
function tulisPath(view) {
  const n = NAV.find(x => x.id === view) || NAV[0];
  const target = '/employee/' + n.path;
  if (location.pathname !== target) history.pushState({ view }, '', target);
}

const state = { view: 'dash', riwayatTab: 'absen', dari: '', sampai: '' };
let DATA = null;
let timerJam = null;

/* ------------------------------------------------------ bootstrap */
(async function mulai() {
  if (!(await mulaiSesi('karyawan'))) return;
  state.view = navDariPath();
  tulisPath(state.view);
  document.title = 'Absensi Saya — ' + (STATE.settings.nama_instansi || '');
  gambarNav();
  await refresh();
})();

function gambarNav() {
  $('#knav').innerHTML = NAV.map(n =>
    '<a href="#" data-nav="' + n.id + '" class="' + (state.view === n.id ? 'on' : '') + '">' + svg(n.icon, 21) + '<span>' + n.label + '</span></a>').join('');
}

document.addEventListener('click', async e => {
  const nav = e.target.closest('[data-nav]');
  if (nav) {
    e.preventDefault();
    state.view = nav.dataset.nav;
    tulisPath(state.view);
    gambarNav();
    await refresh();
  }
});

window.addEventListener('popstate', () => {
  const v = navDariPath();
  if (v !== state.view) { state.view = v; gambarNav(); refresh(); }
});

async function refresh() {
  if (timerJam) { clearInterval(timerJam); timerJam = null; }
  const box = $('#konten');
  box.innerHTML = '<div class="card"><div class="body"><div class="empty">Memuat…</div></div></div>';
  try {
    DATA = await api('/api/dashboard/karyawan');
    if (state.view === 'riwayat') {
      const q = new URLSearchParams();
      if (state.dari) q.set('from', state.dari);
      if (state.sampai) q.set('to', state.sampai);
      DATA.riwayatTask = (await api('/api/tasks/riwayat?' + q.toString())).data;
    }
    box.innerHTML = await (VIEW[state.view] || VIEW.dash)();
    if (state.view === 'dash') timerJam = jamDigital($('#ktime'));
  } catch (err) {
    box.innerHTML = '<div class="card"><div class="body"><div class="empty">Gagal memuat: ' + esc(err.message || err) + '</div></div></div>';
  }
}

const VIEW = {};

/* ------------------------------------------------------ Dashboard absen */
VIEW.dash = function () {
  const k = DATA.karyawan, a = DATA.attendance, s = DATA.settings;
  const bisaMasuk = !a || !a.checkin_at;
  const bisaPulang = a && a.checkin_at && !a.checkout_at;
  const selesai = DATA.task_selesai, total = DATA.task_total;

  const ringkas = [
    ['Jam Masuk', a && a.checkin_at ? fJamDetik(a.checkin_at) : '--:--:--'],
    ['Jam Pulang', a && a.checkout_at ? fJamDetik(a.checkout_at) : '--:--:--'],
    ['Durasi Kerja', a && a.durasi_menit != null ? fDurasi(a.durasi_menit) : '-'],
  ].map(([l, v]) => '<div><b>' + v + '</b><small>' + l + '</small></div>').join('');

  return '' +
  '<div class="kbrand"><img src="/static/logo-word.png" alt="nufatur"><b>' + esc(s.nama_instansi || 'Nufatur Absensi') + '</b></div>' +
  '<div class="khero">' +
    '<img src="/api/foto-profil/' + k.id + '" alt="Foto profil" onerror="this.outerHTML=\'<span class=&quot;av&quot;>' + esc(k.nama.charAt(0)) + '</span>\'">' +
    '<div class="nj"><b>' + esc(k.nama) + '</b><small>' + esc(k.jabatan) + ' · ' + esc(k.divisi || '-') + '</small>' +
    '<div style="margin-top:6px">' + badge(DATA.status_hari_ini) + '</div></div>' +
    '<div class="ktime" id="ktime"></div>' +
  '</div>' +

  '<div class="section-title">' + svg('clock', 16) + 'Absensi Hari Ini<span class="line"></span>' +
    '<span style="color:#5F7385;font-weight:400;font-size:12px">Jam kerja ' + esc(s.jam_masuk) + '–' + esc(s.jam_pulang) + ' ' + esc(s.zona_waktu) + '</span></div>' +

  '<div class="card"><div class="body">' +
    '<div class="today" style="margin-bottom:14px">' + ringkas + '</div>' +
    '<div class="absen-grid">' +
      '<button class="absen-btn in" data-act="absen" data-jenis="masuk"' + (bisaMasuk ? '' : ' disabled') + '>' +
        '<span class="ic">' + svg('camera', 22) + '</span><span>Absen Masuk<small>' + (bisaMasuk ? 'Ambil foto selfie lalu simpan' : 'Sudah absen masuk hari ini') + '</small></span></button>' +
      '<button class="absen-btn out" data-act="absen" data-jenis="pulang"' + (bisaPulang ? '' : ' disabled') + '>' +
        '<span class="ic">' + svg('camera', 22) + '</span><span>Absen Pulang<small>' +
        (bisaPulang ? 'Ambil foto terbaru sebagai bukti pulang' : (a && a.checkin_at ? 'Sudah absen pulang hari ini' : 'Absen masuk dulu')) +
        '</small></span></button>' +
    '</div>' +
    '<div class="cam-note info" style="margin-top:14px">' +
      svg('shield', 16) + '<span>Jam absensi dicatat otomatis oleh server — tidak bisa diubah dari perangkat. Foto wajib diambil langsung dari kamera sebagai bukti kehadiran.</span></div>' +
  '</div></div>' +

  '<div class="section-title">' + svg('checklist', 16) + 'Task Hari Ini<span class="line"></span>' +
    '<span style="color:#5F7385;font-weight:400;font-size:12px">' + selesai + '/' + total + ' selesai</span></div>' +
  '<div class="card"><div class="body">' +
    pbar(DATA.task_persen) + '<div class="ptxt"><span>Progress pekerjaan hari ini</span><span>' + DATA.task_persen + '%</span></div>' +
    '<div style="margin-top:14px">' + (DATA.tasks.length
      ? DATA.tasks.slice(0, 4).map(t => taskItem(t, false)).join('')
      : '<div class="empty">Belum ada jobdesk untuk divisi Anda. Hubungi admin.</div>') + '</div>' +
    (DATA.tasks.length > 4 ? '<button class="btn ghost block" data-nav="task" style="margin-top:4px">Lihat semua ' + DATA.tasks.length + ' jobdesk</button>' : '') +
  '</div></div>' +

  '<div class="section-title">' + svg('report', 16) + 'Riwayat Absensi<span class="line"></span>' +
    '<button class="btn ghost sm" data-nav="riwayat">Semua riwayat</button></div>' +
  '<div class="card"><div class="body">' + riwayatList(DATA.riwayat.slice(0, 5)) + '</div></div>';
};

function taskItem(t, bolehUbah) {
  return '<label class="task' + (t.selesai ? ' done' : '') + '" data-jobdesk="' + t.jobdesk_id + '">' +
    '<input type="checkbox" ' + (t.selesai ? 'checked' : '') + (bolehUbah === false ? ' disabled' : '') + '>' +
    '<span class="tj"><b>' + esc(t.judul) + '</b>' +
    '<small>' + (t.kategori ? esc(t.kategori) + ' · ' : '') + (t.selesai && t.waktu_selesai ? 'Selesai ' + fJamDetik(t.waktu_selesai) : esc(t.deskripsi || 'Belum dikerjakan')) + '</small></span></label>';
}

function riwayatList(rows) {
  if (!rows.length) return '<div class="empty">Belum ada riwayat absensi.</div>';
  return rows.map(r => '<div class="riwayat-item">' +
    '<div style="color:' + (r.status_tampil === 'Hadir' ? '#06B85C' : r.status_tampil === 'Terlambat' ? '#E0900A' : '#D93A3A') + '">' + svg('clock', 18) + '</div>' +
    '<div class="d"><b>' + fHari(r.tanggal) + ', ' + fTanggal(r.tanggal) + '</b>' +
    '<small>' + (r.checkin_at ? 'Masuk ' + fJamDetik(r.checkin_at) : 'Tanpa absen masuk') + ' · ' +
    (r.checkout_at ? 'Pulang ' + fJamDetik(r.checkout_at) : 'Belum absen pulang') + '</small></div>' +
    '<div style="text-align:right">' + badge(r.status_tampil) +
    '<div style="color:#5F7385;font-size:11.5px;margin-top:3px">' + (r.durasi_menit != null ? fDurasi(r.durasi_menit) : '-') + '</div></div>' +
    '</div>').join('');
}

/* ------------------------------------------------------ Task harian */
VIEW.task = function () {
  const selesai = DATA.task_selesai, total = DATA.task_total;
  return '' +
  '<div class="khero" style="margin-bottom:16px">' +
    '<div class="nj"><b>Task Harian</b><small>' + fHari(DATA.tanggal) + ', ' + fTanggal(DATA.tanggal) + '</small></div>' +
    '<div class="ktime" id="ktime"></div></div>' +
  '<div class="card"><div class="body">' +
    pbar(DATA.task_persen) + '<div class="ptxt"><span>' + selesai + ' dari ' + total + ' jobdesk selesai</span><span>' + DATA.task_persen + '%</span></div>' +
    '<div class="cam-note" style="margin-top:14px">' + svg('info', 16) +
    '<span>Centang pekerjaan yang benar-benar Anda kerjakan hari ini. Setiap centang otomatis tersimpan ke database beserta waktunya.</span></div>' +
    '<div style="margin-top:16px">' + (DATA.tasks.length
      ? DATA.tasks.map(t => taskItem(t, true)).join('')
      : '<div class="empty">Belum ada jobdesk untuk divisi Anda. Hubungi admin.</div>') + '</div>' +
  '</div></div>';
};

/* ------------------------------------------------------ Riwayat */
VIEW.riwayat = function () {
  const tab = state.riwayatTab;
  const isiAbsen = riwayatList(DATA.riwayat);
  const tugas = DATA.riwayatTask || [];
  const grup = {};
  tugas.forEach(t => { (grup[t.tanggal] = grup[t.tanggal] || []).push(t); });
  const isiTask = Object.keys(grup).length
    ? Object.keys(grup).sort().reverse().map(tgl => {
        const semua = grup[tgl];
        const selesai = semua.filter(x => x.selesai).length;
        return '<div style="margin-bottom:16px">' +
          '<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">' +
          '<b>' + fHari(tgl) + ', ' + fTanggal(tgl) + '</b>' +
          '<span class="badge ' + (selesai ? 'b-hadir' : 'b-off') + '">' + selesai + ' selesai</span></div>' +
          semua.map(x => '<div class="task' + (x.selesai ? ' done' : '') + '" style="cursor:default">' +
            '<span style="color:' + (x.selesai ? '#06B85C' : '#C3CFDA') + '">' + svg('check', 20) + '</span>' +
            '<span class="tj"><b>' + esc(x.judul) + '</b><small>' + (x.kategori ? esc(x.kategori) + ' · ' : '') +
            (x.selesai ? 'Selesai ' + fJamDetik(x.waktu_selesai) : 'Tidak dikerjakan') + '</small></span></div>').join('') +
          '</div>';
      }).join('')
    : '<div class="empty">Belum ada riwayat task pada periode ini.</div>';

  return '' +
  '<div class="khero" style="margin-bottom:16px"><div class="nj"><b>Riwayat Saya</b><small>Absensi dan task harian</small></div></div>' +
  '<div class="inline" style="margin-bottom:12px">' +
    '<button class="btn ' + (tab === 'absen' ? '' : 'ghost') + '" data-act="tab-riwayat" data-tab="absen">Riwayat Absensi</button>' +
    '<button class="btn ' + (tab === 'task' ? '' : 'ghost') + '" data-act="tab-riwayat" data-tab="task">Riwayat Task</button>' +
  '</div>' +
  (tab === 'task'
    ? '<div class="card"><div class="head"><h3>Riwayat Task</h3><div class="r">' +
      '<input type="date" data-f="dari" value="' + (state.dari || '') + '"><span style="color:#5F7385">s/d</span>' +
      '<input type="date" data-f="sampai" value="' + (state.sampai || '') + '">' +
      '<button class="btn ghost sm" data-act="reset-filter">Reset</button></div></div><div class="body">' + isiTask + '</div></div>'
    : '<div class="card"><div class="head"><h3>Riwayat Absensi (14 terakhir)</h3></div><div class="body">' + isiAbsen + '</div></div>');
};

/* ------------------------------------------------------ Profil */
VIEW.profil = function () {
  const k = DATA.karyawan;
  return '' +
  '<div class="khero" style="margin-bottom:16px">' +
    '<img src="/api/foto-profil/' + k.id + '" alt="Foto profil" id="fprofil">' +
    '<div class="nj"><b>' + esc(k.nama) + '</b><small>' + esc(k.jabatan) + ' · NIK ' + esc(k.nik || '-') + '</small></div>' +
  '</div>' +
  '<div class="card"><div class="head"><h3>Foto Profil</h3></div><div class="body">' +
    '<div style="display:flex;gap:14px;align-items:center;flex-wrap:wrap">' +
      '<img src="/api/foto-profil/' + k.id + '" alt="Foto profil" style="width:96px;height:96px;border-radius:50%;object-fit:cover;border:2px solid #DFE6ED">' +
      '<div class="actions"><button class="btn" data-act="foto-profil">' + svg('camera', 16) + 'Ambil / Ganti Foto</button>' +
      '<button class="btn ghost" data-act="hapus-foto">Hapus Foto</button></div>' +
    '</div></div></div>' +
  '<div class="card"><div class="head"><h3>Data Saya</h3></div><div class="body">' +
    '<div class="form-grid">' +
    '<label class="fld"><span>Nama</span><input type="text" id="pk-nama" value="' + esc(k.nama) + '"></label>' +
    '<label class="fld"><span>Jabatan</span><input type="text" value="' + esc(k.jabatan) + '" disabled></label>' +
    '<label class="fld"><span>Divisi</span><input type="text" value="' + esc(k.divisi || '-') + '" disabled></label>' +
    '<label class="fld"><span>Tanggal Masuk</span><input type="text" value="' + esc(k.tgl_masuk || '-') + '" disabled></label>' +
    '</div><div class="actions" style="margin-top:14px"><button class="btn" data-act="simpan-profil">Simpan Perubahan</button></div>' +
  '</div></div>' +
  '<div class="card"><div class="head"><h3>Ganti Password</h3></div><div class="body">' +
    '<div class="form-grid">' +
    '<label class="fld full"><span>Password Lama</span><input type="password" id="pk-lama"></label>' +
    '<label class="fld"><span>Password Baru</span><input type="password" id="pk-baru"></label>' +
    '<label class="fld"><span>Ulangi Password Baru</span><input type="password" id="pk-ulang"></label>' +
    '</div><div class="actions" style="margin-top:14px"><button class="btn dark" data-act="ganti-pass">Ganti Password</button>' +
    '<button class="btn danger" data-act="logout" style="margin-left:auto">' + svg('logout', 16) + 'Keluar</button></div>' +
  '</div></div>';
};

/* ------------------------------------------------------ aksi */
async function absen(jenis) {
  const set_ = STATE.settings;
  const foto = await ambilFoto({
    judul: jenis === 'masuk' ? 'Absen Masuk — Ambil Foto Selfie' : 'Absen Pulang — Ambil Foto Terbaru',
    keterangan: jenis === 'masuk'
      ? 'Foto selfie menjadi bukti kehadiran Anda hari ini. Pastikan wajah terlihat jelas.'
      : 'Ambil foto terbaru sebagai bukti Anda meninggalkan tempat kerja.',
  });
  if (!foto) return;
  if (set_.wajib_foto && !foto) return toast('Foto wajib diisi untuk absensi.', 'err');
  const r = await api('/api/attendance/' + jenis, { method: 'POST', body: { foto, catatan: '' } });
  if (jenis === 'masuk') {
    toast('Absen masuk tersimpan pukul ' + r.waktu_server + (r.status === 'Terlambat' ? ' — status: Terlambat ' + r.terlambat_menit + ' menit' : ' — status: Hadir'));
  } else {
    toast('Absen pulang tersimpan pukul ' + r.waktu_server + ' — durasi kerja ' + fDurasi(r.attendance.durasi_menit));
  }
  await refresh();
}

document.addEventListener('click', async e => {
  const b = e.target.closest('[data-act]');
  if (!b) return;
  const act = b.dataset.act;
  try {
    switch (act) {
      case 'absen': await absen(b.dataset.jenis); break;
      case 'tab-riwayat': state.riwayatTab = b.dataset.tab; await refresh(); break;
      case 'reset-filter': state.dari = state.sampai = ''; await refresh(); break;
      case 'logout': await keluar(); break;
      case 'simpan-profil':
        await api('/api/profil', { method: 'PUT', body: { nama: $('#pk-nama').value.trim() } });
        toast('Profil diperbarui.');
        await refresh();
        break;
      case 'ganti-pass': {
        const lama = $('#pk-lama').value, baru = $('#pk-baru').value, ulang = $('#pk-ulang').value;
        if (baru !== ulang) return toast('Ulangi password tidak sama.', 'err');
        await api('/api/profil/password', { method: 'POST', body: { lama, baru } });
        toast('Password berhasil diganti.');
        $('#pk-lama').value = $('#pk-baru').value = $('#pk-ulang').value = '';
        break;
      }
      case 'foto-profil': {
        const foto = await ambilFoto({ judul: 'Foto Profil', keterangan: 'Pilih foto yang jelas — dipakai di dashboard dan daftar karyawan.' });
        if (!foto) return;
        await api('/api/profil', { method: 'PUT', body: { foto_profil: foto } });
        toast('Foto profil diperbarui.');
        await refresh();
        break;
      }
      case 'hapus-foto':
        if (await konfirmasi('Hapus foto profil Anda?', { tombol: 'Ya, hapus' })) {
          await api('/api/profil', { method: 'PUT', body: { foto_profil: '' } });
          toast('Foto profil dihapus.');
          await refresh();
        }
        break;
    }
  } catch (err) {
    if (!err.status) toast('Gagal: ' + (err.message || err), 'err');
  }
});

/* checklist task: klik kartu atau checkbox */
document.addEventListener('change', async e => {
  const f = e.target.closest('[data-f]');
  if (f) {
    state[f.dataset.f] = f.value;
    await refresh();
    return;
  }
  const label = e.target.closest('[data-jobdesk]');
  if (!label) return;
  const jid = Number(label.dataset.jobdesk);
  const selesai = e.target.checked;
  e.target.disabled = true;
  try {
    const r = await api('/api/tasks/toggle', { method: 'POST', body: { jobdesk_id: jid, tanggal: DATA.tanggal, selesai } });
    label.classList.toggle('done', selesai);
    toast(selesai ? 'Jobdesk ditandai selesai pukul ' + fJamDetik(r.waktu_selesai) : 'Centang dibatalkan.');
    await refresh();
  } catch (err) {
    e.target.checked = !selesai;
    e.target.disabled = false;
  }
});

/* klik baris task (selain checkbox) juga men-toggle */
document.addEventListener('click', e => {
  const label = e.target.closest('[data-jobdesk]');
  if (!label || e.target.tagName === 'INPUT') return;
  const cb = $('input', label);
  if (cb && !cb.disabled) { cb.checked = !cb.checked; cb.dispatchEvent(new Event('change', { bubbles: true })); }
});
