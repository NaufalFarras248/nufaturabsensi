/* ============================================================
   admin.js — Panel Administrator
   Menu: Dashboard, Data Karyawan, Divisi, Jobdesk, Data Absensi,
         Laporan Task, Laporan Kehadiran, Monitoring, Pengaturan
         Jam Kerja, Pengaturan Akun, Profil.
   ============================================================ */
'use strict';

const MENU = [
  { grp: 'Utama', item: [{ id: 'dashboard', label: 'Dashboard', icon: 'dashboard' }] },
  {
    grp: 'Manajemen', item: [
      { id: 'karyawan', label: 'Data Karyawan', icon: 'users' },
      { id: 'divisi', label: 'Divisi & Kategori', icon: 'shield' },
      { id: 'jobdesk', label: 'Jobdesk Management', icon: 'checklist' },
      { id: 'absensi', label: 'Data Absensi', icon: 'clock' },
    ],
  },
  {
    grp: 'Laporan', item: [
      { id: 'lap-task', label: 'Laporan Task Harian', icon: 'report' },
      { id: 'lap-hadir', label: 'Laporan Kehadiran', icon: 'cal' },
      { id: 'monitor', label: 'Monitoring Aktivitas', icon: 'eye' },
    ],
  },
  {
    grp: 'Sistem', item: [
      { id: 'set-jam', label: 'Pengaturan Jam Kerja', icon: 'settings' },
      { id: 'akun', label: 'Pengaturan Akun', icon: 'key' },
      { id: 'profil', label: 'Profil Saya', icon: 'user' },
    ],
  },
];

const JUDUL = {
  'dashboard': ['Dashboard', 'Ringkasan aktivitas hari ini'],
  'karyawan': ['Data Karyawan', 'Kelola akun dan data seluruh karyawan'],
  'divisi': ['Divisi & Kategori', 'Pembagian divisi kerja perusahaan'],
  'jobdesk': ['Jobdesk Management', 'Daftar pekerjaan yang harus diisi karyawan setiap hari'],
  'absensi': ['Data Absensi', 'Rekap kehadiran, jam kerja, dan bukti foto'],
  'lap-task': ['Laporan Task Harian', 'Penyelesaian jobdesk per karyawan per tanggal'],
  'lap-hadir': ['Laporan Kehadiran', 'Rekap jam masuk, jam pulang, dan durasi kerja'],
  'monitor': ['Monitoring Aktivitas', 'Jejak aktivitas admin dan karyawan'],
  'set-jam': ['Pengaturan Jam Kerja', 'Jam masuk, jam pulang, dan toleransi keterlambatan'],
  'akun': ['Pengaturan Akun', 'Kelola akun login dan password'],
  'profil': ['Profil Saya', 'Data akun yang sedang digunakan'],
};

const awalBulan = () => { const d = new Date(); return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-01'; };

const MENU_IDS = MENU.reduce((a, g) => a.concat(g.item.map(i => i.id)), []);

/** Menu aktif dibaca dari URL: /admin/<menu>. */
function menuDariPath() {
  const s = location.pathname.split('/').filter(Boolean);
  if (s[0] !== 'admin') return 'dashboard';
  return MENU_IDS.includes(s[1]) ? s[1] : 'dashboard';
}
function tulisPath(view) {
  const target = '/admin/' + view;
  if (location.pathname !== target) history.pushState({ view }, '', target);
}

const state = {
  view: 'dashboard',
  tanggal: tglISO(),
  dari: awalBulan(),
  sampai: tglISO(),
  q: '', divisi: '', status: '', kategori: '', karyawan: '', aktif: '',
  absMode: 'hari',
};

let cacheDivisi = [];
let cacheKaryawan = [];

/* ------------------------------------------------------ bootstrap */
(async function mulai() {
  $('#logoBrand').innerHTML = '<img src="/static/logo-mark.png" alt="Logo">';
  $('#hamburger').innerHTML = svg('menu', 20);
  $('#btnLogout').innerHTML = svg('logout', 17) + 'Keluar';
  $('#btnLogout').onclick = keluar;
  $('#hamburger').onclick = () => { $('#sidebar').style.transform = 'translateX(0)'; $('#scrim').style.display = 'block'; };
  $('#scrim').onclick = () => { $('#sidebar').style.transform = ''; $('#scrim').style.display = 'none'; };
  if (!(await mulaiSesi('admin'))) return;
  state.view = menuDariPath();
  tulisPath(state.view);
  $('#whoName').textContent = STATE.user.nama || STATE.user.username;
  $('#whoRole').textContent = 'Administrator';
  $('#avatar').textContent = (STATE.user.nama || 'A').trim().charAt(0).toUpperCase();
  $('#namaInstansi').textContent = STATE.settings.nama_instansi || 'Nufatur Absensi';
  document.title = 'Admin — ' + (STATE.settings.nama_instansi || 'Nufatur Absensi');
  jamDigital($('#clock'));
  gambarNav();
  await refresh();
  setInterval(async () => {
    try { const d = await api('/api/me', { silent: true }); $('#jamServer').textContent = fJamDetik(d.jam_server); } catch (e) { /* diam */ }
  }, 30000);
})();

function gambarNav() {
  $('#nav').innerHTML = MENU.map(g =>
    '<div class="grp">' + esc(g.grp) + '</div>' +
    g.item.map(i => '<a href="#" data-nav="' + i.id + '" class="' + (state.view === i.id ? 'on' : '') + '">' +
      svg(i.icon, 18) + '<span>' + esc(i.label) + '</span></a>').join('')
  ).join('');
}

document.addEventListener('click', e => {
  const nav = e.target.closest('[data-nav]');
  if (nav) {
    e.preventDefault();
    state.view = nav.dataset.nav;
    tulisPath(state.view);
    if (window.innerWidth <= 900) { $('#sidebar').style.transform = ''; $('#scrim').style.display = 'none'; }
    gambarNav();
    refresh();
  }
});

// tombol maju/mundur browser
window.addEventListener('popstate', () => {
  const v = menuDariPath();
  if (v !== state.view) { state.view = v; gambarNav(); refresh(); }
});

/* ------------------------------------------------------ render utama */
async function refresh() {
  const [t, s] = JUDUL[state.view] || ['', ''];
  $('#pageTitle').textContent = t;
  $('#pageSub').textContent = s;
  const box = $('#content');
  box.innerHTML = '<div class="card"><div class="body"><div class="empty">Memuat data…</div></div></div>';
  try {
    box.innerHTML = await (VIEW[state.view] || VIEW.dashboard)();
  } catch (err) {
    box.innerHTML = '<div class="card"><div class="body"><div class="empty">Gagal memuat: ' + esc(err.message || err) + '</div></div></div>';
  }
}

const VIEW = {};

/* ------------------------------------------------------ Dashboard */
VIEW.dashboard = async function () {
  const d = await api('/api/dashboard/admin?tanggal=' + state.tanggal);
  const r = d.ringkasan;
  const kartu = (ikon, warna, lbl, val, sm) =>
    '<div class="stat"><div class="ic ' + warna + '">' + svg(ikon, 20) + '</div><div><div class="lbl">' + lbl + '</div>' +
    '<div class="val">' + val + '</div><div class="sm">' + (sm || '') + '</div></div></div>';

  const rows = d.karyawan.map(k => '<tr>' +
    '<td><b>' + esc(k.nama) + '</b><div class="sm" style="color:#94a3b8;font-size:11.5px">' + esc(k.jabatan) + '</div></td>' +
    '<td>' + esc(k.divisi || '-') + '</td>' +
    '<td>' + (k.checkin_at ? fJamDetik(k.checkin_at) : '<span style="color:#D93A3A">-</span>') + '</td>' +
    '<td>' + (k.checkout_at ? fJamDetik(k.checkout_at) : '-') + '</td>' +
    '<td>' + (k.terlambat_menit > 0 ? '<span style="color:#b45309">+' + k.terlambat_menit + ' mnt</span>' : '-') + '</td>' +
    '<td>' + badge(k.status_tampil) + '</td>' +
    '<td style="min-width:130px">' + pbar(k.task_persen) + '<div class="ptxt"><span>' + k.task_selesai + '/' + k.task_target + ' jobdesk</span><span>' + k.task_persen + '%</span></div></td>' +
    '<td class="actions nowrap">' +
    (k.att_id ? '<button class="btn ghost sm" data-act="lihat-absen" data-id="' + k.att_id + '">' + svg('eye', 15) + 'Detail</button>' : '<span style="color:#94a3b8;font-size:12px">belum absen</span>') +
    '<button class="btn ghost sm" data-act="lihat-checklist" data-id="' + k.id + '" data-nama="' + esc(k.nama) + '" data-tgl="' + d.tanggal + '">' + svg('checklist', 15) + 'Checklist</button>' +
    '</td>' +
    '</tr>').join('');

  const aktivitas = (d.aktivitas || []).map(a => '<div class="riwayat-item"><div style="color:#1D7AB7">' + svg('info', 17) + '</div>' +
    '<div class="d"><b>' + esc(a.aksi.replace(/_/g, ' ')) + '</b><small>' + esc(a.username || 'sistem') + ' · ' + esc(a.detail || '') + '</small></div>' +
    '<small style="color:#94a3b8">' + fJamDetik(a.created_at) + '</small></div>').join('') || '<div class="empty">Belum ada aktivitas.</div>';

  return '' +
    '<div class="inline" style="margin-bottom:14px">' +
    '<label>Tanggal <input type="date" data-f="tanggal" value="' + state.tanggal + '"></label>' +
    '<button class="btn ghost sm" data-act="hari-ini">Hari ini</button>' +
    '<span class="badge b-blue">Jam server: ' + esc(d.jam_server) + '</span>' +
    '</div>' +
    '<div class="grid g-auto" style="margin-bottom:18px">' +
    kartu('users', '', 'Total Karyawan Aktif', r.total_karyawan) +
    kartu('check', 'green', 'Sudah Absen Masuk', r.sudah_absen, r.sudah_absen + ' dari ' + r.total_karyawan) +
    kartu('close', 'red', 'Belum Absen', r.belum_absen) +
    kartu('clock', 'amber', 'Terlambat', r.terlambat) +
    kartu('logout', 'green', 'Sudah Absen Pulang', r.sudah_pulang) +
    kartu('checklist', '', 'Task Selesai Hari Ini', r.task_selesai + '/' + r.task_target, r.task_persen + '% dari total jobdesk aktif') +
    '</div>' +
    '<div class="card"><div class="head"><h3>Absensi Karyawan — ' + fHari(d.tanggal) + ', ' + fTanggal(d.tanggal) + '</h3>' +
    '<div class="r"><button class="btn ghost sm" data-act="export-hadir-pdf">' + svg('download', 15) + 'PDF</button>' +
    '<button class="btn ghost sm" data-act="export-hadir-xlsx">' + svg('download', 15) + 'Excel</button></div></div>' +
    '<div class="body tight tw"><table><thead><tr><th>Nama</th><th>Divisi</th><th>Masuk</th><th>Pulang</th><th>Terlambat</th><th>Status</th><th>Progress Jobdesk</th><th>Aksi</th></tr></thead>' +
    '<tbody>' + (rows || '<tr><td colspan="8" class="empty">Belum ada karyawan aktif.</td></tr>') + '</tbody></table></div></div>' +
    '<div class="card"><div class="head"><h3>Aktivitas Terbaru</h3></div><div class="body">' + aktivitas + '</div></div>';
};

/* ------------------------------------------------------ Data Karyawan */
async function muatMaster() {
  const [d, k] = await Promise.all([api('/api/divisions'), api('/api/employees')]);
  cacheDivisi = d.data;
  cacheKaryawan = k.data;
}
const opsiDivisi = (pilih) => '<option value="">Semua divisi</option>' + cacheDivisi.map(d =>
  '<option value="' + d.id + '"' + (String(pilih) === String(d.id) ? ' selected' : '') + '>' + esc(d.nama) + '</option>').join('');
const opsiKaryawan = (pilih) => '<option value="">Semua karyawan</option>' + cacheKaryawan.map(k =>
  '<option value="' + k.id + '"' + (String(pilih) === String(k.id) ? ' selected' : '') + '>' + esc(k.nama) + '</option>').join('');

VIEW.karyawan = async function () {
  await muatMaster();
  const q = new URLSearchParams();
  if (state.q) q.set('q', state.q);
  if (state.divisi) q.set('division_id', state.divisi);
  if (state.status) q.set('status', state.status);
  const d = await api('/api/employees?' + q.toString());
  const rows = d.data.map(k => '<tr>' +
    '<td><b>' + esc(k.nama) + '</b><div class="sm" style="color:#94a3b8;font-size:11.5px">' + esc(k.email || '-') + '</div></td>' +
    '<td>' + esc(k.nik || '-') + '</td>' +
    '<td>' + esc(k.jabatan || '-') + '</td>' +
    '<td>' + esc(k.divisi || '-') + '</td>' +
    '<td>' + esc(k.telepon || '-') + '</td>' +
    '<td>' + badge(k.status) + '</td>' +
    '<td>' + (k.username ? '<b>' + esc(k.username) + '</b><div class="sm" style="color:#94a3b8;font-size:11.5px">' + (k.akun_aktif ? 'akun aktif' : 'akun nonaktif') + '</div>' : '<span class="badge b-off">belum ada akun</span>') + '</td>' +
    '<td class="actions nowrap">' +
    '<button class="btn ghost sm" data-act="edit-kar" data-id="' + k.id + '">' + svg('edit', 14) + 'Edit</button>' +
    (k.username
      ? '<button class="btn ghost sm" data-act="reset-pass" data-id="' + k.id + '" data-nama="' + esc(k.nama) + '">' + svg('key', 14) + 'Password</button>'
      : '<button class="btn sm" data-act="buat-akun" data-id="' + k.id + '" data-nama="' + esc(k.nama) + '">' + svg('key', 14) + 'Buat Akun</button>') +
    '<button class="btn danger sm" data-act="hapus-kar" data-id="' + k.id + '" data-nama="' + esc(k.nama) + '">' + svg('trash', 14) + '</button>' +
    '</td></tr>').join('');

  return '' +
    '<div class="card"><div class="head"><h3>Daftar Karyawan (' + d.data.length + ')</h3><div class="r">' +
    '<input type="text" placeholder="Cari nama / NIK / jabatan…" data-search="q" value="' + esc(state.q) + '" style="padding:8px 11px;border:1px solid #C3CFDA;border-radius:9px;min-width:210px">' +
    '<select data-f="divisi">' + opsiDivisi(state.divisi) + '</select>' +
    '<select data-f="status"><option value="">Semua status</option><option value="aktif"' + (state.status === 'aktif' ? ' selected' : '') + '>Aktif</option><option value="nonaktif"' + (state.status === 'nonaktif' ? ' selected' : '') + '>Nonaktif</option></select>' +
    '<button class="btn" data-act="tambah-kar">' + svg('plus', 16) + 'Tambah Karyawan</button>' +
    '</div></div>' +
    '<div class="body tight tw"><table><thead><tr><th>Nama</th><th>NIK</th><th>Jabatan</th><th>Divisi</th><th>Kontak</th><th>Status</th><th>Akun Login</th><th>Aksi</th></tr></thead>' +
    '<tbody>' + (rows || '<tr><td colspan="8" class="empty">Tidak ada data karyawan.</td></tr>') + '</tbody></table></div></div>';
};

/* ------------------------------------------------------ Divisi */
VIEW.divisi = async function () {
  const d = await api('/api/divisions');
  cacheDivisi = d.data;
  const rows = d.data.map(x => '<tr><td><b>' + esc(x.nama) + '</b></td><td>' + esc(x.keterangan || '-') + '</td>' +
    '<td class="num">' + x.jml_karyawan + '</td>' +
    '<td class="actions"><button class="btn ghost sm" data-act="edit-div" data-id="' + x.id + '">' + svg('edit', 14) + 'Edit</button>' +
    '<button class="btn danger sm" data-act="hapus-div" data-id="' + x.id + '" data-nama="' + esc(x.nama) + '">' + svg('trash', 14) + '</button></td></tr>').join('');
  const jd = await api('/api/jobdesks');
  const kategori = [...new Set(jd.data.map(j => j.kategori).filter(Boolean))];
  return '' +
    '<div class="card"><div class="head"><h3>Divisi (' + d.data.length + ')</h3><div class="r"><button class="btn" data-act="tambah-div">' + svg('plus', 16) + 'Tambah Divisi</button></div></div>' +
    '<div class="body tight tw"><table><thead><tr><th>Nama Divisi</th><th>Keterangan</th><th class="num">Jumlah Karyawan</th><th>Aksi</th></tr></thead><tbody>' +
    (rows || '<tr><td colspan="4" class="empty">Belum ada divisi.</td></tr>') + '</tbody></table></div></div>' +
    '<div class="card"><div class="head"><h3>Kategori Jobdesk Terpakai (' + kategori.length + ')</h3></div><div class="body">' +
    (kategori.length ? kategori.map(k => '<span class="badge b-blue" style="margin:0 6px 6px 0">' + esc(k) + '</span>').join('') : '<div class="empty">Belum ada kategori.</div>') +
    '<div style="color:#5F7385;font-size:12.5px;margin-top:8px">Kategori diisi saat membuat atau mengedit jobdesk.</div></div></div>';
};

/* ------------------------------------------------------ Jobdesk */
VIEW.jobdesk = async function () {
  await muatMaster();
  const q = new URLSearchParams();
  if (state.divisi) q.set('division_id', state.divisi);
  if (state.kategori) q.set('kategori', state.kategori);
  if (state.aktif !== '') q.set('aktif', state.aktif);
  const d = await api('/api/jobdesks?' + q.toString());
  const rows = d.data.map(j => '<tr>' +
    '<td><b>' + esc(j.judul) + '</b><div class="sm" style="color:#94a3b8;font-size:11.5px">' + esc(j.deskripsi || '') + '</div></td>' +
    '<td>' + (j.kategori ? '<span class="badge b-blue">' + esc(j.kategori) + '</span>' : '-') + '</td>' +
    '<td>' + esc(j.divisi || 'Semua divisi') + '</td>' +
    '<td>' + (j.aktif ? '<span class="badge b-hadir"><i class="dot"></i>Aktif</span>' : '<span class="badge b-off"><i class="dot"></i>Nonaktif</span>') + '</td>' +
    '<td class="actions nowrap"><button class="btn ghost sm" data-act="edit-jd" data-id="' + j.id + '">' + svg('edit', 14) + 'Edit</button>' +
    '<button class="btn ghost sm" data-act="toggle-jd" data-id="' + j.id + '" data-aktif="' + j.aktif + '">' + (j.aktif ? 'Nonaktifkan' : 'Aktifkan') + '</button>' +
    '<button class="btn danger sm" data-act="hapus-jd" data-id="' + j.id + '" data-nama="' + esc(j.judul) + '">' + svg('trash', 14) + '</button></td></tr>').join('');
  const kat = d.kategori || [];
  return '' +
    '<div class="card"><div class="head"><h3>Daftar Jobdesk (' + d.data.length + ')</h3><div class="r">' +
    '<select data-f="kategori"><option value="">Semua kategori</option>' + kat.map(k => '<option' + (state.kategori === k ? ' selected' : '') + '>' + esc(k) + '</option>').join('') + '</select>' +
    '<select data-f="divisi">' + opsiDivisi(state.divisi) + '</select>' +
    '<select data-f="aktif"><option value="">Semua</option><option value="1"' + (state.aktif === '1' ? ' selected' : '') + '>Aktif</option><option value="0"' + (state.aktif === '0' ? ' selected' : '') + '>Nonaktif</option></select>' +
    '<button class="btn" data-act="tambah-jd">' + svg('plus', 16) + 'Tambah Jobdesk</button></div></div>' +
    '<div class="body tight tw"><table><thead><tr><th>Jobdesk</th><th>Kategori</th><th>Berlaku Untuk</th><th>Status</th><th>Aksi</th></tr></thead><tbody>' +
    (rows || '<tr><td colspan="5" class="empty">Belum ada jobdesk.</td></tr>') + '</tbody></table></div>' +
    '<div class="body" style="border-top:1px solid #DFE6ED;color:#5F7385;font-size:12.5px">' +
    'Jobdesk tanpa divisi berlaku untuk semua karyawan. Jobdesk dengan divisi hanya muncul di checklist karyawan divisi tersebut.</div></div>';
};

/* ------------------------------------------------------ Data Absensi */
VIEW.absensi = async function () {
  await muatMaster();
  const q = new URLSearchParams();
  if (state.absMode === 'hari') q.set('tanggal', state.tanggal);
  else { q.set('from', state.dari); q.set('to', state.sampai); }
  if (state.karyawan) q.set('employee_id', state.karyawan);
  if (state.divisi) q.set('division_id', state.divisi);
  if (state.status) q.set('status', state.status);
  if (state.q) q.set('q', state.q);
  const d = await api('/api/attendance?' + q.toString());
  const set_ = STATE.settings;
  const rows = d.data.map(a => '<tr>' +
    '<td class="nowrap">' + fTanggal(a.tanggal) + '<div class="sm" style="color:#94a3b8;font-size:11.5px">' + fHari(a.tanggal) + '</div></td>' +
    '<td><b>' + esc(a.nama) + '</b><div class="sm" style="color:#94a3b8;font-size:11.5px">' + esc(a.jabatan) + ' · ' + esc(a.divisi || '-') + '</div></td>' +
    '<td class="nowrap">' + fJamDetik(a.checkin_at) + '</td>' +
    '<td class="nowrap">' + fJamDetik(a.checkout_at) + '</td>' +
    '<td>' + (a.durasi_menit != null ? fDurasi(a.durasi_menit) : '-') + '</td>' +
    '<td>' + (a.terlambat_menit > 0 ? '<span style="color:#b45309">' + a.terlambat_menit + ' mnt</span>' : '-') + '</td>' +
    '<td>' + badge(a.status_tampil) + '</td>' +
    '<td class="actions nowrap">' +
    (a.foto_masuk ? '<img class="thumb" src="/api/photo/' + a.foto_masuk + '" data-act="lihat-foto" data-id="' + a.id + '" alt="foto masuk" title="Foto masuk">' : '<span class="badge b-off" title="tanpa foto">-</span>') +
    (a.foto_pulang ? '<img class="thumb" src="/api/photo/' + a.foto_pulang + '" data-act="lihat-foto" data-id="' + a.id + '" alt="foto pulang" title="Foto pulang">' : '') +
    '<button class="btn ghost sm" data-act="lihat-absen" data-id="' + a.id + '">' + svg('eye', 14) + '</button>' +
    '<button class="btn ghost sm" data-act="lihat-checklist" data-id="' + a.employee_id + '" data-nama="' + esc(a.nama) + '" data-tgl="' + a.tanggal + '" title="Checklist pekerjaan">' + svg('checklist', 14) + '</button>' +
    '</td></tr>').join('');

  return '' +
    '<div class="card"><div class="head"><h3>Filter Data Absensi</h3><div class="r">' +
    '<div class="inline">' +
    '<label>Mode <select data-f="absMode"><option value="hari"' + (state.absMode === 'hari' ? ' selected' : '') + '>Per hari</option><option value="rentang"' + (state.absMode === 'rentang' ? ' selected' : '') + '>Rentang tanggal</option></select></label>' +
    (state.absMode === 'hari'
      ? '<label>Tanggal <input type="date" data-f="tanggal" value="' + state.tanggal + '"></label>'
      : '<label>Dari <input type="date" data-f="dari" value="' + state.dari + '"></label><label>s/d <input type="date" data-f="sampai" value="' + state.sampai + '"></label>') +
    '<label>Karyawan <select data-f="karyawan">' + opsiKaryawan(state.karyawan) + '</select></label>' +
    '<label>Divisi <select data-f="divisi">' + opsiDivisi(state.divisi) + '</select></label>' +
    '<label>Status <select data-f="status"><option value="">Semua</option>' +
    ['telat|Hanya terlambat', 'pulang|Sudah absen pulang', 'belum_pulang|Belum absen pulang'].map(o => {
      const [v, t] = o.split('|');
      return '<option value="' + v + '"' + (state.status === v ? ' selected' : '') + '>' + t + '</option>';
    }).join('') + '</select></label>' +
    '<input type="text" placeholder="Cari nama…" data-search="q" value="' + esc(state.q) + '" style="padding:8px 11px;border:1px solid #C3CFDA;border-radius:9px;min-width:160px">' +
    '<button class="btn ghost sm" data-act="export-hadir-xlsx">' + svg('download', 15) + 'Excel</button>' +
    '<button class="btn ghost sm" data-act="export-hadir-pdf">' + svg('download', 15) + 'PDF</button>' +
    '</div></div></div>' +
    '<div class="body tight tw"><table><thead><tr><th>Tanggal</th><th>Karyawan</th><th>Masuk</th><th>Pulang</th><th>Durasi</th><th>Telat</th><th>Status</th><th>Bukti Foto</th></tr></thead>' +
    '<tbody>' + (rows || '<tr><td colspan="8" class="empty">Tidak ada data absensi pada filter ini.</td></tr>') + '</tbody></table></div>' +
    '<div class="body" style="border-top:1px solid #DFE6ED;color:#5F7385;font-size:12.5px">' +
    'Jam kerja standar ' + esc(set_.jam_masuk) + '–' + esc(set_.jam_pulang) + ' dengan toleransi ' + set_.toleransi_menit +
    ' menit. Semua jam dicatat dari waktu server. Klik foto untuk melihat bukti absensi ukuran penuh.</div></div>';
};

/* ------------------------------------------------------ Laporan Task */
VIEW['lap-task'] = async function () {
  await muatMaster();
  const q = new URLSearchParams({ from: state.dari, to: state.sampai });
  if (state.divisi) q.set('division_id', state.divisi);
  if (state.karyawan) q.set('employee_id', state.karyawan);
  if (state.q) q.set('q', state.q);
  const d = await api('/api/reports/tasks?' + q.toString());
  const rows = d.data.map(t => '<tr>' +
    '<td class="nowrap">' + fTanggal(t.tanggal) + '</td>' +
    '<td><b>' + esc(t.nama) + '</b><div class="sm" style="color:#94a3b8;font-size:11.5px">' + esc(t.jabatan) + ' · ' + esc(t.divisi || '-') + '</div></td>' +
    '<td class="num">' + (t.selesai || 0) + ' / ' + t.target + '</td>' +
    '<td style="min-width:120px">' + pbar(t.persen) + '<div class="ptxt"><span>' + t.persen + '%</span></div></td>' +
    '<td style="font-size:12.5px">' + esc((t.judul_selesai || '').split('; ').filter(Boolean).join(' · ') || '-') + '</td></tr>').join('');
  return '' +
    '<div class="card"><div class="head"><h3>Filter Laporan Task</h3><div class="r"><div class="inline">' +
    '<label>Dari <input type="date" data-f="dari" value="' + state.dari + '"></label>' +
    '<label>s/d <input type="date" data-f="sampai" value="' + state.sampai + '"></label>' +
    '<label>Divisi <select data-f="divisi">' + opsiDivisi(state.divisi) + '</select></label>' +
    '<label>Karyawan <select data-f="karyawan">' + opsiKaryawan(state.karyawan) + '</select></label>' +
    '<input type="text" placeholder="Cari nama…" data-search="q" value="' + esc(state.q) + '" style="padding:8px 11px;border:1px solid #C3CFDA;border-radius:9px;min-width:150px">' +
    '<button class="btn ghost sm" data-act="export-task-xlsx">' + svg('download', 15) + 'Excel</button>' +
    '<button class="btn ghost sm" data-act="export-task-pdf">' + svg('download', 15) + 'PDF</button>' +
    '</div></div></div>' +
    '<div class="header" style="padding:12px 16px;background:#f8fafc;border-bottom:1px solid #DFE6ED;display:flex;gap:16px;flex-wrap:wrap">' +
    '<div><small style="color:#5F7385">Baris data</small><div><b>' + d.jumlah + '</b></div></div>' +
    '<div><small style="color:#5F7385">Total jobdesk selesai</small><div><b>' + d.ringkasan.selesai + '</b></div></div>' +
    '<div><small style="color:#5F7385">Rata-rata penyelesaian</small><div><b>' + d.ringkasan.rata_persen + '%</b></div></div></div>' +
    '<div class="body tight tw"><table><thead><tr><th>Tanggal</th><th>Karyawan</th><th class="num">Selesai / Target</th><th>Penyelesaian</th><th>Pekerjaan yang diselesaikan</th></tr></thead>' +
    '<tbody>' + (rows || '<tr><td colspan="5" class="empty">Belum ada task tercatat pada periode ini.</td></tr>') + '</tbody></table></div></div>';
};

/* ------------------------------------------------------ Laporan Kehadiran */
VIEW['lap-hadir'] = async function () {
  await muatMaster();
  const q = new URLSearchParams({ from: state.dari, to: state.sampai });
  if (state.divisi) q.set('division_id', state.divisi);
  if (state.karyawan) q.set('employee_id', state.karyawan);
  if (state.q) q.set('q', state.q);
  const d = await api('/api/reports/attendance?' + q.toString());
  const rows = d.data.map(a => '<tr>' +
    '<td class="nowrap">' + fTanggal(a.tanggal) + '</td>' +
    '<td><b>' + esc(a.nama) + '</b><div class="sm" style="color:#94a3b8;font-size:11.5px">' + esc(a.jabatan) + ' · ' + esc(a.divisi || '-') + '</div></td>' +
    '<td>' + fJam(a.checkin_at) + '</td><td>' + fJam(a.checkout_at) + '</td>' +
    '<td>' + a.durasi_jam.toFixed(2) + ' jam</td>' +
    '<td>' + (a.terlambat_menit > 0 ? a.terlambat_menit + ' mnt' : '-') + '</td>' +
    '<td>' + badge(a.status_tampil) + '</td>' +
    '<td>' + (a.bukti_foto === 'lengkap' ? '<span class="badge b-hadir">lengkap</span>' : a.bukti_foto === 'masuk' ? '<span class="badge b-telat">masuk saja</span>' : '<span class="badge b-off">tidak ada</span>') + '</td>' +
    '<td>' + pbar(a.task_persen) + '<div class="ptxt"><span>' + a.task_selesai + '/' + a.task_target + '</span><span>' + a.task_persen + '%</span></div></td>' +
    '<td><button class="btn ghost sm" data-act="lihat-absen" data-id="' + a.id + '">' + svg('eye', 14) + '</button></td></tr>').join('');
  return '' +
    '<div class="card"><div class="head"><h3>Filter Laporan Kehadiran</h3><div class="r"><div class="inline">' +
    '<label>Dari <input type="date" data-f="dari" value="' + state.dari + '"></label>' +
    '<label>s/d <input type="date" data-f="sampai" value="' + state.sampai + '"></label>' +
    '<label>Divisi <select data-f="divisi">' + opsiDivisi(state.divisi) + '</select></label>' +
    '<label>Karyawan <select data-f="karyawan">' + opsiKaryawan(state.karyawan) + '</select></label>' +
    '<input type="text" placeholder="Cari nama…" data-search="q" value="' + esc(state.q) + '" style="padding:8px 11px;border:1px solid #C3CFDA;border-radius:9px;min-width:150px">' +
    '<button class="btn ghost sm" data-act="export-hadir-xlsx">' + svg('download', 15) + 'Excel</button>' +
    '<button class="btn ghost sm" data-act="export-hadir-pdf">' + svg('download', 15) + 'PDF</button>' +
    '<button class="btn ghost sm" data-act="cetak">' + svg('report', 15) + 'Cetak</button>' +
    '</div></div></div>' +
    '<div style="padding:12px 16px;background:#f8fafc;border-bottom:1px solid #DFE6ED;display:flex;gap:18px;flex-wrap:wrap">' +
    '<div><small style="color:#5F7385">Baris data</small><div><b>' + d.jumlah + '</b></div></div>' +
    '<div><small style="color:#5F7385">Hadir tepat waktu</small><div><b>' + d.ringkasan.hadir + '</b></div></div>' +
    '<div><small style="color:#5F7385">Terlambat</small><div><b>' + d.ringkasan.terlambat + '</b></div></div>' +
    '<div><small style="color:#5F7385">Total jam kerja</small><div><b>' + d.ringkasan.total_jam + ' jam</b></div></div>' +
    '<div><small style="color:#5F7385">Rata-rata task</small><div><b>' + d.ringkasan.rata_task + '%</b></div></div></div>' +
    '<div class="body tight tw"><table><thead><tr><th>Tanggal</th><th>Karyawan</th><th>Masuk</th><th>Pulang</th><th>Durasi</th><th>Telat</th><th>Status</th><th>Bukti</th><th>Task</th><th></th></tr></thead>' +
    '<tbody>' + (rows || '<tr><td colspan="10" class="empty">Belum ada data kehadiran pada periode ini.</td></tr>') + '</tbody></table></div></div>';
};

/* ------------------------------------------------------ Monitoring */
VIEW.monitor = async function () {
  const d = await api('/api/log?limit=200');
  const rows = d.data.map(l => '<tr><td class="nowrap">' + esc(l.created_at) + '</td>' +
    '<td>' + esc(l.username || 'sistem') + '</td><td>' + badge(l.role || 'sistem') + '</td>' +
    '<td><b>' + esc(l.aksi.replace(/_/g, ' ')) + '</b></td><td>' + esc(l.detail || '') + '</td></tr>').join('');
  return '<div class="card"><div class="head"><h3>Jejak Aktivitas (200 terakhir)</h3></div>' +
    '<div class="body tight tw"><table><thead><tr><th>Waktu</th><th>User</th><th>Role</th><th>Aksi</th><th>Detail</th></tr></thead>' +
    '<tbody>' + (rows || '<tr><td colspan="5" class="empty">Belum ada aktivitas.</td></tr>') + '</tbody></table></div></div>';
};

/* ------------------------------------------------------ Pengaturan Jam Kerja */
VIEW['set-jam'] = async function () {
  const s = STATE.settings;
  const hari = ['Minggu', 'Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu'];
  const dipilih = String(s.hari_kerja || '').split(',');
  return '<div class="card"><div class="head"><h3>Pengaturan Jam Kerja &amp; Toleransi</h3></div><div class="body">' +
    '<div class="form-grid">' +
    '<label class="fld"><span>Nama Instansi</span><input type="text" id="s-instansi" value="' + esc(s.nama_instansi) + '"></label>' +
    '<label class="fld"><span>Zona Waktu</span><input type="text" id="s-zona" value="' + esc(s.zona_waktu) + '" placeholder="WIB"></label>' +
    '<label class="fld"><span>Jam Masuk</span><input type="time" id="s-masuk" value="' + esc(s.jam_masuk) + '"></label>' +
    '<label class="fld"><span>Jam Pulang</span><input type="time" id="s-pulang" value="' + esc(s.jam_pulang) + '"></label>' +
    '<label class="fld"><span>Toleransi Keterlambatan (menit)</span><input type="number" id="s-tol" min="0" max="240" value="' + s.toleransi_menit + '"></label>' +
    '<label class="fld"><span>Wajib Foto Selfie Absensi</span><select id="s-foto"><option value="1"' + (s.wajib_foto ? ' selected' : '') + '>Ya, wajib</option><option value="0"' + (!s.wajib_foto ? ' selected' : '') + '>Tidak wajib</option></select></label>' +
    '<div class="fld full"><span>Hari Kerja</span><div class="inline" id="s-hari">' +
    hari.map((h, i) => '<label class="switch"><input type="checkbox" value="' + i + '"' + (dipilih.includes(String(i)) ? ' checked' : '') + '> ' + h + '</label>').join('') +
    '</div><div class="hint">Absensi tetap bisa dilakukan di hari non-kerja, tetapi laporan menandainya sebagai hari libur.</div></div>' +
    '</div>' +
    '<div class="actions" style="margin-top:16px"><button class="btn" data-act="simpan-set">' + svg('check', 16) + 'Simpan Pengaturan</button>' +
    '<span style="color:#5F7385;font-size:12.5px;align-self:center">Terakhir diubah: ' + esc(s.updated_at || '-') + '</span></div>' +
    '<div style="margin-top:16px;background:var(--brand-50);border:1px solid var(--brand-100);color:var(--brand-800);padding:12px 14px;border-radius:10px;font-size:12.5px">' +
    'Keterlambatan dihitung otomatis dari jam masuk server dibanding jam masuk kerja + toleransi. Karyawan tidak bisa mengubah jam absensi.</div>' +
    '</div></div>';
};

/* ------------------------------------------------------ Pengaturan Akun */
VIEW.akun = async function () {
  const d = await api('/api/users');
  const rows = d.data.map(u => '<tr>' +
    '<td><b>' + esc(u.username) + '</b><div class="sm" style="color:#94a3b8;font-size:11.5px">' + esc(u.email || '-') + '</div></td>' +
    '<td>' + esc(u.nama || 'Administrator') + '</td>' +
    '<td>' + badge(u.role) + '</td>' +
    '<td>' + (u.aktif ? '<span class="badge b-hadir"><i class="dot"></i>Aktif</span>' : '<span class="badge b-off"><i class="dot"></i>Nonaktif</span>') + '</td>' +
    '<td class="nowrap">' + esc(u.last_login || 'belum pernah') + '</td>' +
    '<td class="actions nowrap">' +
    '<button class="btn ghost sm" data-act="ubah-akun" data-id="' + u.id + '" data-user="' + esc(u.username) + '">' + svg('edit', 14) + 'Ubah</button>' +
    '<button class="btn ' + (u.aktif ? 'danger' : 'success') + ' sm" data-act="toggle-akun" data-id="' + u.id + '" data-aktif="' + u.aktif + '">' + (u.aktif ? 'Nonaktifkan' : 'Aktifkan') + '</button>' +
    '</td></tr>').join('');
  return '<div class="card"><div class="head"><h3>Akun Login (' + d.data.length + ')</h3></div>' +
    '<div class="body tight tw"><table><thead><tr><th>Username</th><th>Nama</th><th>Role</th><th>Status</th><th>Login Terakhir</th><th>Aksi</th></tr></thead>' +
    '<tbody>' + (rows || '<tr><td colspan="6" class="empty">Belum ada akun.</td></tr>') + '</tbody></table></div>' +
    '<div class="body" style="border-top:1px solid #DFE6ED;color:#5F7385;font-size:12.5px">' +
    'Akun karyawan dibuat dari menu Data Karyawan. Di sini admin bisa mengganti username, mereset password, atau menonaktifkan akun.</div></div>';
};

/* ------------------------------------------------------ Profil */
VIEW.profil = async function () {
  const d = await api('/api/profil');
  const k = d.karyawan;
  return '' +
    '<div class="grid g2">' +
    '<div class="card"><div class="head"><h3>Data Profil</h3></div><div class="body">' +
    '<div class="form-grid">' +
    '<label class="fld"><span>Username</span><input type="text" id="p-user" value="' + esc(d.user.username) + '"></label>' +
    '<label class="fld"><span>Email</span><input type="email" id="p-email" value="' + esc(d.user.email || (k ? k.email : '') || '') + '"></label>' +
    (k ? '<label class="fld"><span>Nama</span><input type="text" id="p-nama" value="' + esc(k.nama) + '"></label>' +
      '<label class="fld"><span>Telepon</span><input type="text" id="p-telp" value="' + esc(k.telepon || '') + '"></label>' : '') +
    '</div>' +
    '<div class="actions" style="margin-top:14px"><button class="btn" data-act="simpan-profil">' + svg('check', 16) + 'Simpan Profil</button></div>' +
    '<div style="margin-top:12px;color:#5F7385;font-size:12.5px">Role: <b>' + esc(d.user.role) + '</b> · Login terakhir: ' + esc(d.user.last_login || '-') + '</div>' +
    '</div></div>' +
    '<div class="card"><div class="head"><h3>Ganti Password</h3></div><div class="body">' +
    '<div class="form-grid">' +
    '<label class="fld full"><span>Password Lama</span><input type="password" id="pw-lama" autocomplete="current-password"></label>' +
    '<label class="fld"><span>Password Baru</span><input type="password" id="pw-baru" autocomplete="new-password"></label>' +
    '<label class="fld"><span>Ulangi Password Baru</span><input type="password" id="pw-ulang" autocomplete="new-password"></label>' +
    '</div><div class="hint" style="color:#5F7385;font-size:12px;margin-top:8px">Minimal 6 karakter. Sesi di perangkat lain akan otomatis keluar.</div>' +
    '<div class="actions" style="margin-top:14px"><button class="btn dark" data-act="simpan-pass">' + svg('key', 16) + 'Ganti Password</button></div>' +
    '</div></div></div>';
};

/* ====================================================== AKSI & MODAL */
document.addEventListener('change', async e => {
  const f = e.target.closest('[data-f]');
  if (f) {
    state[f.dataset.f] = f.value;
    if (['divisi', 'status'].includes(f.dataset.f) && state.view === 'karyawan') { /* tetap */ }
    await refresh();
    return;
  }
  const cb = e.target.closest('[data-check-jobdesk]');
  if (cb) {
    const emp = Number(cb.dataset.emp), tgl = cb.dataset.tgl, nama = cb.dataset.nama;
    cb.disabled = true;
    try {
      await api('/api/tasks/toggle', {
        method: 'POST',
        body: { employee_id: emp, jobdesk_id: Number(cb.dataset.checkJobdesk), tanggal: tgl, selesai: cb.checked ? 1 : 0 },
      });
      toast(cb.checked ? 'Jobdesk ditandai selesai oleh admin.' : 'Centang dibatalkan oleh admin.');
      await muatModalChecklist(emp, nama, tgl);
    } catch (err) {
      cb.checked = !cb.checked;
      cb.disabled = false;
    }
    return;
  }
  if (e.target.id === 'imp-foto') return;
});

let timerCari = null;
document.addEventListener('input', e => {
  const s = e.target.closest('[data-search]');
  if (!s) return;
  clearTimeout(timerCari);
  const v = s.value;
  timerCari = setTimeout(async () => {
    state[s.dataset.search] = v;
    const fokus = document.activeElement === s;
    await refresh();
    if (fokus) {
      const lagi = $('[data-search="' + s.dataset.search + '"]');
      if (lagi) { lagi.focus(); lagi.setSelectionRange(lagi.value.length, lagi.value.length); }
    }
  }, 420);
});

document.addEventListener('click', async e => {
  const b = e.target.closest('[data-act]');
  if (!b) return;
  const act = b.dataset.act, id = Number(b.dataset.id || 0);
  try {
    switch (act) {
      case 'hari-ini': state.tanggal = tglISO(); await refresh(); break;
      case 'cetak': window.print(); break;

      /* ---- export ---- */
      case 'export-hadir-xlsx': await unduhFile('/api/export/xlsx?jenis=kehadiran&' + qLaporan(), 'laporan-kehadiran.xlsx'); break;
      case 'export-hadir-pdf': await unduhFile('/api/export/pdf?jenis=kehadiran&' + qLaporan(), 'laporan-kehadiran.pdf'); break;
      case 'export-task-xlsx': await unduhFile('/api/export/xlsx?jenis=task&' + qLaporan(), 'laporan-task.xlsx'); break;
      case 'export-task-pdf': await unduhFile('/api/export/pdf?jenis=task&' + qLaporan(), 'laporan-task.pdf'); break;

      /* ---- karyawan ---- */
      case 'tambah-kar': await formKaryawan(null); break;
      case 'edit-kar': await formKaryawan(id); break;
      case 'hapus-kar':
        if (await konfirmasi('Hapus karyawan <b>' + esc(b.dataset.nama) + '</b>?<br><br>Seluruh riwayat absensi, foto, dan checklist task karyawan ini akan ikut terhapus permanen.', { judul: 'Hapus Karyawan', tombol: 'Ya, hapus' })) {
          await api('/api/employees/' + id, { method: 'DELETE' });
          toast('Karyawan dihapus.');
          await refresh();
        }
        break;
      case 'buat-akun': await modalBuatAkun(id, b.dataset.nama); break;
      case 'reset-pass': await modalResetPass(id, b.dataset.nama); break;

      /* ---- divisi ---- */
      case 'tambah-div': await formDivisi(null); break;
      case 'edit-div': await formDivisi(id); break;
      case 'hapus-div':
        if (await konfirmasi('Hapus divisi <b>' + esc(b.dataset.nama) + '</b>?', { tombol: 'Ya, hapus' })) {
          await api('/api/divisions/' + id, { method: 'DELETE' });
          toast('Divisi dihapus.');
          await refresh();
        }
        break;

      /* ---- jobdesk ---- */
      case 'tambah-jd': await formJobdesk(null); break;
      case 'edit-jd': await formJobdesk(id); break;
      case 'toggle-jd': {
        const aktif = b.dataset.aktif === '1' ? 0 : 1;
        const d = await api('/api/jobdesks');
        const j = d.data.find(x => x.id === id);
        await api('/api/jobdesks/' + id, { method: 'PUT', body: { judul: j.judul, kategori: j.kategori, division_id: j.division_id, deskripsi: j.deskripsi, aktif } });
        toast(aktif ? 'Jobdesk diaktifkan.' : 'Jobdesk dinonaktifkan.');
        await refresh();
        break;
      }
      case 'hapus-jd':
        if (await konfirmasi('Hapus jobdesk <b>' + esc(b.dataset.nama) + '</b>?<br><br>Checklist karyawan yang memakai jobdesk ini ikut terhapus.', { tombol: 'Ya, hapus' })) {
          await api('/api/jobdesks/' + id, { method: 'DELETE' });
          toast('Jobdesk dihapus.');
          await refresh();
        }
        break;

      /* ---- absensi ---- */
      case 'lihat-absen': await modalAbsen(id); break;
      case 'lihat-foto': await modalAbsen(id); break;
      case 'lihat-checklist': await modalChecklist(Number(b.dataset.id), b.dataset.nama, b.dataset.tgl); break;

      /* ---- akun ---- */
      case 'ubah-akun': await modalUbahAkun(id, b.dataset.user); break;
      case 'toggle-akun': {
        await api('/api/users/' + id, { method: 'PUT', body: { aktif: b.dataset.aktif === '1' ? 0 : 1 } });
        toast('Status akun diperbarui.');
        await refresh();
        break;
      }

      /* ---- pengaturan ---- */
      case 'simpan-set': {
        const hari = $$('#s-hari input:checked').map(i => Number(i.value));
        const r = await api('/api/settings', {
          method: 'PUT',
          body: {
            nama_instansi: $('#s-instansi').value, zona_waktu: $('#s-zona').value,
            jam_masuk: $('#s-masuk').value, jam_pulang: $('#s-pulang').value,
            toleransi_menit: Number($('#s-tol').value), wajib_foto: Number($('#s-foto').value),
            hari_kerja: hari,
          },
        });
        STATE.settings = r.settings;
        $('#namaInstansi').textContent = r.settings.nama_instansi;
        toast('Pengaturan jam kerja disimpan.');
        await refresh();
        break;
      }
      case 'simpan-profil': {
        const body = { username: $('#p-user').value, email: $('#p-email').value };
        if ($('#p-nama')) { body.nama = $('#p-nama').value; body.telepon = $('#p-telp').value; }
        await api('/api/profil', { method: 'PUT', body });
        toast('Profil diperbarui.');
        await mulaiSesi('admin');
        await refresh();
        break;
      }
      case 'simpan-pass': {
        const lama = $('#pw-lama').value, baru = $('#pw-baru').value, ulang = $('#pw-ulang').value;
        if (baru !== ulang) { toast('Ulangi password tidak sama.', 'err'); break; }
        await api('/api/profil/password', { method: 'POST', body: { lama, baru } });
        toast('Password berhasil diganti.');
        $('#pw-lama').value = $('#pw-baru').value = $('#pw-ulang').value = '';
        break;
      }
    }
  } catch (err) {
    if (!err.status) toast('Gagal: ' + (err.message || err), 'err');
  }
});

function qLaporan() {
  const q = new URLSearchParams({ from: state.absMode === 'hari' && state.view === 'dashboard' ? state.tanggal : state.dari, to: state.absMode === 'hari' && state.view === 'dashboard' ? state.tanggal : state.sampai });
  if (state.view === 'dashboard') { q.set('from', state.tanggal); q.set('to', state.tanggal); }
  if (state.divisi) q.set('division_id', state.divisi);
  if (state.karyawan) q.set('employee_id', state.karyawan);
  if (state.q) q.set('q', state.q);
  return q.toString();
}

/* ---------------- Modal: karyawan ---------------- */
async function formKaryawan(id) {
  if (!cacheDivisi.length) await muatMaster();
  const k = id ? (await api('/api/employees?' + (state.q ? 'q=' + encodeURIComponent(state.q) : ''))).data.find(x => x.id === id) || (await api('/api/employees')).data.find(x => x.id === id) : null;
  const v = x => (k && k[x] != null ? esc(k[x]) : '');
  const isi =
    '<div class="form-grid">' +
    '<label class="fld full"><span>Nama Lengkap *</span><input type="text" id="k-nama" value="' + v('nama') + '" required></label>' +
    '<label class="fld"><span>NIK / ID Karyawan</span><input type="text" id="k-nik" value="' + v('nik') + '"></label>' +
    '<label class="fld"><span>Jabatan</span><input type="text" id="k-jabatan" value="' + v('jabatan') + '"></label>' +
    '<label class="fld"><span>Divisi</span><select id="k-div"><option value="">- tanpa divisi -</option>' +
    cacheDivisi.map(d => '<option value="' + d.id + '"' + (k && k.division_id === d.id ? ' selected' : '') + '>' + esc(d.nama) + '</option>').join('') + '</select></label>' +
    '<label class="fld"><span>Status</span><select id="k-status"><option value="aktif"' + (!k || k.status === 'aktif' ? ' selected' : '') + '>Aktif</option><option value="nonaktif"' + (k && k.status === 'nonaktif' ? ' selected' : '') + '>Nonaktif</option></select></label>' +
    '<label class="fld"><span>Email</span><input type="email" id="k-email" value="' + v('email') + '"></label>' +
    '<label class="fld"><span>Telepon</span><input type="text" id="k-telp" value="' + v('telepon') + '"></label>' +
    '<label class="fld"><span>Tanggal Masuk</span><input type="date" id="k-masuk" value="' + (k ? String(k.tgl_masuk || '').slice(0, 10) : tglISO()) + '"></label>' +
    (k ? '<label class="fld full"><span>Reset Password Akun (opsional)</span><input type="text" id="k-pass" placeholder="biarkan kosong bila tidak diubah"><div class="hint">Minimal 6 karakter.</div></label>'
      : '<div class="fld full"><label class="switch"><input type="checkbox" id="k-buatakun" checked> Buatkan akun login untuk karyawan ini</label></div>' +
      '<label class="fld"><span>Username (opsional)</span><input type="text" id="k-user" placeholder="otomatis dari nama depan"></label>' +
      '<label class="fld"><span>Password (opsional)</span><input type="text" id="k-pass2" placeholder="otomatis dibuat sistem"></label>') +
    '</div>';
  const m = bukaModal({
    judul: k ? 'Edit Karyawan' : 'Tambah Karyawan',
    isi,
    aksi: '<button class="btn ghost" data-close>Batal</button><button class="btn" data-simpan>' + svg('check', 16) + 'Simpan</button>',
  });
  $('[data-simpan]', m).onclick = async () => {
    const body = {
      nama: $('#k-nama', m).value.trim(), nik: $('#k-nik', m).value.trim(), jabatan: $('#k-jabatan', m).value.trim(),
      division_id: $('#k-div', m).value || null, status: $('#k-status', m).value,
      email: $('#k-email', m).value.trim(), telepon: $('#k-telp', m).value.trim(), tgl_masuk: $('#k-masuk', m).value,
    };
    if (!body.nama) return toast('Nama wajib diisi.', 'err');
    if (k) {
      const pw = $('#k-pass', m).value.trim();
      if (pw) body.password = pw;
      await api('/api/employees/' + k.id, { method: 'PUT', body });
      toast('Data karyawan diperbarui.');
    } else {
      if ($('#k-buatakun', m).checked) {
        body.buat_akun = 1;
        const u = $('#k-user', m).value.trim();
        const p = $('#k-pass2', m).value.trim();
        if (u) body.username = u;
        if (p) body.password = p;
      }
      const r = await api('/api/employees', { method: 'POST', body });
      tutupModal();
      await refresh();
      if (r.akun) {
        await konfirmasi('Karyawan dibuat dengan akun login:<br><br><b>Username:</b> ' + esc(r.akun) + '<br><b>Password:</b> ' + esc(r.password_awal) +
          '<br><br>Catat password ini sekarang — tidak ditampilkan lagi.', { judul: 'Akun Berhasil Dibuat', tombol: 'Sudah dicatat', bahaya: false });
        return;
      }
      toast('Karyawan ditambahkan.');
      return;
    }
    tutupModal();
    await refresh();
  };
}

function modalBuatAkun(id, nama) {
  const m = bukaModal({
    judul: 'Buat Akun Login — ' + nama,
    isi: '<div class="form-grid">' +
      '<label class="fld full"><span>Username</span><input type="text" id="a-user" placeholder="otomatis dari nama depan"></label>' +
      '<label class="fld full"><span>Password</span><input type="text" id="a-pass" placeholder="otomatis dibuat sistem (min 6 karakter)"></label>' +
      '</div><div class="hint" style="color:#5F7385;font-size:12.5px;margin-top:10px">Karyawan memakai akun ini untuk login dan melakukan absensi.</div>',
    aksi: '<button class="btn ghost" data-close>Batal</button><button class="btn" data-simpan>' + svg('key', 16) + 'Buat Akun</button>',
  });
  $('[data-simpan]', m).onclick = async () => {
    const body = {};
    const u = $('#a-user', m).value.trim(), p = $('#a-pass', m).value.trim();
    if (u) body.username = u;
    if (p) body.password = p;
    const r = await api('/api/employees/' + id + '/akun', { method: 'POST', body });
    tutupModal();
    await konfirmasi('Akun login dibuat:<br><br><b>Username:</b> ' + esc(r.username) + '<br><b>Password:</b> ' + esc(r.password_awal) +
      '<br><br>Catat sekarang — tidak ditampilkan lagi.', { judul: 'Akun Dibuat', tombol: 'Sudah dicatat', bahaya: false });
    await refresh();
  };
}

function modalResetPass(id, nama) {
  const m = bukaModal({
    judul: 'Reset Password — ' + nama,
    isi: '<label class="fld"><span>Password Baru</span><input type="text" id="r-pass" placeholder="minimal 6 karakter"></label>' +
      '<div class="hint" style="color:#5F7385;font-size:12.5px;margin-top:10px">Semua sesi login karyawan ini akan keluar otomatis.</div>',
    aksi: '<button class="btn ghost" data-close>Batal</button><button class="btn danger" data-simpan>' + svg('key', 16) + 'Reset Password</button>',
  });
  $('[data-simpan]', m).onclick = async () => {
    const p = $('#r-pass', m).value.trim();
    if (p.length < 6) return toast('Password minimal 6 karakter.', 'err');
    await api('/api/employees/' + id, { method: 'PUT', body: { password: p } });
    tutupModal();
    toast('Password karyawan direset.');
  };
}

function modalUbahAkun(id, username) {
  const m = bukaModal({
    judul: 'Ubah Akun — ' + username,
    isi: '<div class="form-grid">' +
      '<label class="fld"><span>Username</span><input type="text" id="u-user" value="' + esc(username) + '"></label>' +
      '<label class="fld"><span>Password Baru (opsional)</span><input type="text" id="u-pass" placeholder="biarkan kosong"></label>' +
      '</div>',
    aksi: '<button class="btn ghost" data-close>Batal</button><button class="btn" data-simpan>' + svg('check', 16) + 'Simpan</button>',
  });
  $('[data-simpan]', m).onclick = async () => {
    const body = { username: $('#u-user', m).value.trim() };
    const p = $('#u-pass', m).value.trim();
    if (p) {
      if (p.length < 6) return toast('Password minimal 6 karakter.', 'err');
      body.password = p;
    }
    await api('/api/users/' + id, { method: 'PUT', body });
    tutupModal();
    toast('Akun diperbarui.');
    await refresh();
  };
}

function formDivisi(id) {
  const x = cacheDivisi.find(d => d.id === id);
  const m = bukaModal({
    judul: x ? 'Edit Divisi' : 'Tambah Divisi',
    isi: '<div class="form-grid">' +
      '<label class="fld full"><span>Nama Divisi *</span><input type="text" id="d-nama" value="' + (x ? esc(x.nama) : '') + '"></label>' +
      '<label class="fld full"><span>Keterangan</span><textarea id="d-ket">' + (x ? esc(x.keterangan || '') : '') + '</textarea></label></div>',
    aksi: '<button class="btn ghost" data-close>Batal</button><button class="btn" data-simpan>Simpan</button>',
  });
  $('[data-simpan]', m).onclick = async () => {
    const body = { nama: $('#d-nama', m).value.trim(), keterangan: $('#d-ket', m).value.trim() };
    if (body.nama.length < 2) return toast('Nama divisi minimal 2 karakter.', 'err');
    if (x) await api('/api/divisions/' + x.id, { method: 'PUT', body });
    else await api('/api/divisions', { method: 'POST', body });
    tutupModal();
    toast('Divisi disimpan.');
    await refresh();
  };
}

function formJobdesk(id) {
  const isi =
    '<div class="form-grid">' +
    '<label class="fld full"><span>Judul Jobdesk *</span><input type="text" id="j-judul" placeholder="contoh: Membuat laporan harian"></label>' +
    '<label class="fld"><span>Kategori</span><input type="text" id="j-kat" placeholder="Administrasi / Gudang / IT"></label>' +
    '<label class="fld"><span>Berlaku Untuk Divisi</span><select id="j-div"><option value="">Semua divisi</option>' +
    cacheDivisi.map(d => '<option value="' + d.id + '">' + esc(d.nama) + '</option>').join('') + '</select></label>' +
    '<label class="fld full"><span>Deskripsi</span><textarea id="j-desc" placeholder="Penjelasan singkat pekerjaan"></textarea></label>' +
    '<label class="fld"><span>Status</span><select id="j-aktif"><option value="1">Aktif</option><option value="0">Nonaktif</option></select></label>' +
    '</div>';
  const m = bukaModal({ judul: id ? 'Edit Jobdesk' : 'Tambah Jobdesk', isi, aksi: '<button class="btn ghost" data-close>Batal</button><button class="btn" data-simpan>Simpan</button>' });
  if (id) {
    api('/api/jobdesks').then(d => {
      const j = d.data.find(x => x.id === id);
      if (!j) return;
      $('#j-judul', m).value = j.judul;
      $('#j-kat', m).value = j.kategori || '';
      $('#j-div', m).value = j.division_id || '';
      $('#j-desc', m).value = j.deskripsi || '';
      $('#j-aktif', m).value = String(j.aktif);
    });
  }
  $('[data-simpan]', m).onclick = async () => {
    const body = {
      judul: $('#j-judul', m).value.trim(), kategori: $('#j-kat', m).value.trim(),
      division_id: $('#j-div', m).value || null, deskripsi: $('#j-desc', m).value.trim(),
      aktif: Number($('#j-aktif', m).value),
    };
    if (body.judul.length < 3) return toast('Judul jobdesk minimal 3 karakter.', 'err');
    if (id) await api('/api/jobdesks/' + id, { method: 'PUT', body });
    else await api('/api/jobdesks', { method: 'POST', body });
    tutupModal();
    toast('Jobdesk disimpan.');
    await refresh();
  };
}

/* ---------------- Modal: detail absensi + foto ---------------- */
async function modalAbsen(attId) {
  const d = await api('/api/attendance?tanggal=' + state.tanggal);
  let a = d.data.find(x => x.id === attId);
  if (!a) {
    const semua = await api('/api/attendance?from=' + awalBulan() + '&to=' + tglISO());
    a = semua.data.find(x => x.id === attId);
  }
  if (!a) return toast('Data absensi tidak ditemukan.', 'err');
  const foto = (id, label, jam) => id
    ? '<div style="flex:1;min-width:230px"><div style="font-weight:700;margin-bottom:6px">' + label + ' <span style="color:#5F7385;font-weight:400">' + esc(jam) + '</span></div>' +
      '<img class="photo" src="/api/photo/' + id + '" alt="' + label + '"></div>'
    : '<div style="flex:1;min-width:230px"><div style="font-weight:700;margin-bottom:6px">' + label + '</div>' +
      '<div class="empty" style="border:1px dashed #C3CFDA;border-radius:10px">Tidak ada foto bukti</div></div>';
  bukaModal({
    judul: 'Detail Absensi — ' + a.nama,
    lebar: 'wide',
    isi: '<div class="grid g2" style="margin-bottom:14px">' +
      '<div><div style="color:#5F7385;font-size:12px">TANGGAL</div><b>' + fHari(a.tanggal) + ', ' + fTanggal(a.tanggal) + '</b></div>' +
      '<div><div style="color:#5F7385;font-size:12px">STATUS</div>' + badge(a.status_tampil) + '</div>' +
      '<div><div style="color:#5F7385;font-size:12px">JABATAN / DIVISI</div><b>' + esc(a.jabatan) + ' · ' + esc(a.divisi || '-') + '</b></div>' +
      '<div><div style="color:#5F7385;font-size:12px">DURASI KERJA</div><b>' + fDurasi(a.durasi_menit) + '</b></div>' +
      '<div><div style="color:#5F7385;font-size:12px">JAM MASUK (server)</div><b>' + fJamDetik(a.checkin_at) + '</b></div>' +
      '<div><div style="color:#5F7385;font-size:12px">JAM PULANG (server)</div><b>' + fJamDetik(a.checkout_at) + '</b></div>' +
      '</div>' +
      '<div class="inline" style="margin-bottom:14px">' +
      '<span class="badge b-blue">Terlambat: ' + a.terlambat_menit + ' menit</span>' +
      '<span class="badge b-off">Sumber waktu: server</span>' +
      (a.catatan ? '<span class="badge b-off">Catatan: ' + esc(a.catatan) + '</span>' : '') + '</div>' +
      '<div style="display:flex;gap:14px;flex-wrap:wrap">' +
      foto(a.foto_masuk, 'FOTO ABSEN MASUK', fJamDetik(a.checkin_at)) +
      foto(a.foto_pulang, 'FOTO ABSEN PULANG', fJamDetik(a.checkout_at)) +
      '</div>',
    aksi: '<button class="btn ghost" data-close>Tutup</button>',
  });
}

/* ---------------- Modal: checklist pekerjaan karyawan (admin) ---------------- */
async function modalChecklist(employeeId, nama, tanggal) {
  bukaModal({
    judul: 'Checklist Pekerjaan — ' + nama,
    isi: '<div id="cl-body"><div class="empty">Memuat checklist…</div></div>',
    aksi: '<button class="btn ghost" data-close>Tutup</button>',
  });
  await muatModalChecklist(employeeId, nama, tanggal);
}

async function muatModalChecklist(employeeId, nama, tanggal) {
  const box = document.getElementById('cl-body');
  if (!box) return;
  const d = await api('/api/tasks?employee_id=' + employeeId + '&tanggal=' + tanggal);
  const item = t => '<label class="task' + (t.selesai ? ' done' : '') + '" style="margin-bottom:8px">' +
    '<input type="checkbox" data-check-jobdesk="' + t.jobdesk_id + '" data-emp="' + employeeId + '" data-tgl="' + tanggal + '" data-nama="' + esc(nama) + '"' + (t.selesai ? ' checked' : '') + '>' +
    '<span class="tj"><b>' + esc(t.judul) + '</b><small>' +
    (t.kategori ? esc(t.kategori) + ' · ' : '') + (t.divisi ? 'divisi ' + esc(t.divisi) : 'berlaku semua divisi') + ' · ' +
    (t.selesai && t.waktu_selesai ? 'selesai pukul ' + fJamDetik(t.waktu_selesai) : 'belum dikerjakan') +
    '</small></span></label>';
  box.innerHTML =
    '<div class="inline" style="margin-bottom:12px">' +
    '<span class="badge b-blue">' + esc(fHari(tanggal)) + ', ' + fTanggal(tanggal) + '</span>' +
    '<span class="badge b-off">' + esc(d.karyawan.jabatan) + ' · ' + esc(d.karyawan.divisi || '-') + '</span>' +
    '<span class="badge ' + (d.persen >= 100 ? 'b-hadir' : d.persen > 0 ? 'b-telat' : 'b-absen') + '">' + d.selesai + ' dari ' + d.total + ' jobdesk (' + d.persen + '%)</span>' +
    '</div>' +
    pbar(d.persen) +
    '<div style="margin:14px 0 4px">' + (d.data.length ? d.data.map(item).join('') : '<div class="empty">Belum ada jobdesk untuk divisi karyawan ini.</div>') + '</div>' +
    '<div class="hint" style="color:#5F7385;font-size:12.5px">Centang di sini untuk mengoreksi checklist karyawan. Perubahan tercatat atas nama admin pada Monitoring Aktivitas.</div>';
}
