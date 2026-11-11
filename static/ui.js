/* ============================================================
   ui.js — modul bersama: panggilan API, ikon, modal, toast,
   dialog konfirmasi, dan kamera selfie.
   ============================================================ */
'use strict';

const $ = (s, r) => (r || document).querySelector(s);
const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
const el = (tag, attrs, html) => {
  const n = document.createElement(tag);
  Object.assign(n, attrs || {});
  if (html != null) n.innerHTML = html;
  return n;
};

/* ---------------- Ikon (SVG inline, satu gaya) ---------------- */
const ICON = {
  dashboard: '<path d="M4 13h6v7H4zM4 4h6v6H4zM14 4h6v10h-6zM14 17h6v3h-6z"/>',
  users: '<path d="M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm7 0a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM2 20c0-3.3 3.1-6 7-6s7 2.7 7 6v1H2v-1Zm15-5c2.8.2 5 2.4 5 5v1h-4v-1c0-1.8-.7-3.5-1.9-4.8h.9Z"/>',
  clock: '<path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm1 5v5.6l3.8 2.2-.9 1.5L11 13.4V7h2Z"/>',
  checklist: '<path d="M3 5h2.2v2.2H3zM7.5 5H21v2.2H7.5zM3 10.9h2.2v2.2H3zM7.5 10.9H21v2.2H7.5zM3 16.8h2.2v2.2H3zM7.5 16.8H21v2.2H7.5z"/>',
  report: '<path d="M5 3h9l5 5v13H5V3Zm8 1.6V9h4.4L13 4.6ZM8 12h8v2H8v-2Zm0 4h8v2H8v-2Z"/>',
  settings: '<path d="M12 8.2a3.8 3.8 0 1 0 0 7.6 3.8 3.8 0 0 0 0-7.6Zm9.2 3.8c0 .6-.1 1.2-.2 1.7l2 1.5-2 3.4-2.3-.9c-.9.7-1.9 1.2-2.9 1.5L15.4 22h-3.9l-.4-2.4c-1.1-.3-2.1-.8-2.9-1.5l-2.3.9-2-3.4 2-1.5a8.6 8.6 0 0 1 0-3.4l-2-1.5 2-3.4 2.3.9c.9-.7 1.9-1.2 2.9-1.5l.4-2.4h3.9l.4 2.4c1.1.3 2.1.8 2.9 1.5l2.3-.9 2 3.4-2 1.5c.1.5.2 1.1.2 1.7Z"/>',
  logout: '<path d="M10 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h5v-2H5V5h5V3Zm5.6 3.6L21 12l-5.4 5.4-1.4-1.4 3-3H9v-2h8.2l-3-3 1.4-1.4Z"/>',
  camera: '<path d="M9 3h6l1.6 2H20a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h3.4L9 3Zm3 5a5 5 0 1 0 0 10 5 5 0 0 0 0-10Zm0 2.6a2.4 2.4 0 1 1 0 4.8 2.4 2.4 0 0 1 0-4.8Z"/>',
  download: '<path d="M12 3v10.2l3.3-3.3 1.4 1.4-5.7 5.7-5.7-5.7 1.4-1.4L10 13.2V3h2ZM4 19h16v2H4z"/>',
  search: '<path d="M10 3a7 7 0 1 0 4.2 12.6l4.1 4.1 1.4-1.4-4.1-4.1A7 7 0 0 0 10 3Zm0 2a5 5 0 1 1 0 10 5 5 0 0 1 0-10Z"/>',
  plus: '<path d="M11 4h2v7h7v2h-7v7h-2v-7H4v-2h7V4Z"/>',
  edit: '<path d="M4 20h4l10-10-4-4L4 16v4Zm12.7-12.7 1.6-1.6a1 1 0 0 0 0-1.4l-.6-.6a1 1 0 0 0-1.4 0l-1.6 1.6 2 2Z"/>',
  trash: '<path d="M9 3h6l1 2h4v2H4V5h4l1-2ZM6 9h12l-1 12H7L6 9Z"/>',
  eye: '<path d="M12 5c5 0 9 4.3 9 7s-4 7-9 7-9-4.3-9-7 4-7 9-7Zm0 3.4a3.6 3.6 0 1 0 0 7.2 3.6 3.6 0 0 0 0-7.2Z"/>',
  key: '<path d="M14 3a7 7 0 1 0-6.3 10L6 15v3H3v3h6l1-1v-2h2l1-2v-1l1.6-1.6A7 7 0 0 0 14 3Zm2 4.5a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0Z"/>',
  menu: '<path d="M3 6h18v2H3zM3 11h18v2H3zM3 16h18v2H3z"/>',
  cal: '<path d="M7 2v2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2h-2V2h-2v2H9V2H7Zm12 8v10H5V10h14Z"/>',
  check: '<path d="M9.6 16.2 5.4 12l-1.4 1.4 5.6 5.6L20.4 8.2 19 6.8z"/>',
  close: '<path d="m12 10.6 5-5L18.4 7l-5 5 5 5L17 18.4l-5-5-5 5L5.6 17l5-5-5-5L7 5.6z"/>',
  info: '<path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm1 15h-2v-6h2v6Zm0-8h-2V7h2v2Z"/>',
  shield: '<path d="M12 2 4 5v7c0 5 3.4 9.3 8 10 4.6-.7 8-5 8-10V5l-8-3Zm-1 13-3-3 1.4-1.4L11 12.2l4.6-4.6L17 9l-6 6Z"/>',
  user: '<path d="M12 12a5 5 0 1 0 0-10 5 5 0 0 0 0 10Zm0 2c-4.4 0-8 2.4-8 5.4V22h16v-2.6c0-3-3.6-5.4-8-5.4Z"/>',
};
function svg(name, size = 18) {
  return '<svg viewBox="0 0 24 24" width="' + size + '" height="' + size + '" fill="currentColor" aria-hidden="true">' + (ICON[name] || '') + '</svg>';
}

/* ---------------- Format ---------------- */
const HARI = ['Minggu', 'Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu'];
const BULAN = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'];
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const pad2 = n => String(n).padStart(2, '0');
const tglISO = d => (d || new Date()).toISOString().slice(0, 10);
function fTanggal(iso) {
  if (!iso) return '-';
  const [y, m, d] = String(iso).slice(0, 10).split('-').map(Number);
  return d + ' ' + BULAN[(m || 1) - 1] + ' ' + y;
}
function fHari(iso) {
  const [y, m, d] = String(iso).slice(0, 10).split('-').map(Number);
  return HARI[new Date(y, m - 1, d).getDay()];
}
const fJam = ts => (ts ? String(ts).slice(11, 16) : '-');
const fJamDetik = ts => (ts ? String(ts).slice(11, 19) : '-');
function fDurasi(menit) {
  if (menit == null) return '-';
  const j = Math.floor(menit / 60), m = menit % 60;
  return (j ? j + ' jam ' : '') + m + ' mnt';
}
const BADGE = {
  'Hadir': 'b-hadir', 'Terlambat': 'b-telat', 'Belum Absen Pulang': 'b-belum', 'Tidak Hadir': 'b-absen',
  'aktif': 'b-hadir', 'nonaktif': 'b-off', 'admin': 'b-blue', 'karyawan': 'b-off',
};
const badge = s => '<span class="badge ' + (BADGE[s] || 'b-off') + '"><i class="dot"></i>' + esc(s) + '</span>';

/* ---------------- Notifikasi ---------------- */
function toast(pesan, tipe) {
  const w = $('#toasts') || el('div', { id: 'toasts' });
  if (!w.parentNode) document.body.appendChild(w);
  const t = el('div', { className: 'toast ' + (tipe || 'ok') });
  t.textContent = pesan;
  w.appendChild(t);
  setTimeout(() => { t.style.opacity = '0'; t.style.transition = 'opacity .25s'; setTimeout(() => t.remove(), 260); }, tipe === 'err' ? 4200 : 2600);
}

/* ---------------- Modal ---------------- */
let modalTerbuka = null;
function bukaModal({ judul, isi, aksi, lebar }) {
  tutupModal();
  const m = el('div', { className: 'modal' + (lebar === 'wide' ? ' wide' : '') });
  m.innerHTML =
    '<div class="mh"><h3>' + esc(judul) + '</h3><button class="x" data-close aria-label="Tutup">' + svg('close', 20) + '</button></div>' +
    '<div class="mb">' + (typeof isi === 'string' ? isi : '') + '</div>' +
    (aksi ? '<div class="mf">' + aksi + '</div>' : '');
  if (typeof isi !== 'string') $('.mb', m).appendChild(isi);
  const mask = el('div', { className: 'mask' });
  mask.appendChild(m);
  mask.addEventListener('click', e => { if (e.target === mask || e.target.closest('[data-close]')) tutupModal(); });
  document.body.appendChild(mask);
  modalTerbuka = mask;
  document.body.style.overflow = 'hidden';
  return m;
}
function tutupModal() {
  if (modalTerbuka) { modalTerbuka.remove(); modalTerbuka = null; }
  document.body.style.overflow = '';
}
document.addEventListener('keydown', e => { if (e.key === 'Escape') tutupModal(); });

function konfirmasi(pesan, { judul = 'Konfirmasi', tombol = 'Ya, lanjutkan', bahaya = true } = {}) {
  return new Promise(res => {
    const m = bukaModal({
      judul,
      isi: '<div style="display:flex;gap:12px;align-items:flex-start"><div style="color:' + (bahaya ? '#D93A3A' : '#1D7AB7') + '">' + svg('info', 30) + '</div>' +
        '<div>' + pesan + '</div></div>',
      aksi: '<button class="btn ghost" data-no>Batal</button><button class="btn ' + (bahaya ? 'danger' : '') + '" data-yes>' + esc(tombol) + '</button>',
    });
    m.addEventListener('click', e => {
      if (e.target.closest('[data-no]')) { tutupModal(); res(false); }
      if (e.target.closest('[data-yes]')) { tutupModal(); res(true); }
    });
  });
}

/* ---------------- API ---------------- */
const STATE = { user: null, csrf: '', settings: {}, jamServer: '' };

async function api(path, { method = 'GET', body = null, silent = false } = {}) {
  const opt = { method, credentials: 'same-origin', headers: {} };
  if (body !== null) {
    opt.headers['Content-Type'] = 'application/json';
    opt.headers['X-CSRF'] = STATE.csrf;
    opt.body = JSON.stringify(body);
  } else if (method !== 'GET') {
    opt.headers['X-CSRF'] = STATE.csrf;
  }
  let r;
  try {
    r = await fetch(path, opt);
  } catch (e) {
    if (!silent) toast('Tidak bisa menghubungi server. Pastikan server.py masih berjalan.', 'err');
    throw new Error('jaringan');
  }
  if (r.status === 401) {
    if (!silent) { toast('Sesi berakhir, silakan login ulang.', 'err'); setTimeout(() => location.href = '/', 900); }
    throw new Error('unauthorized');
  }
  const isJson = (r.headers.get('Content-Type') || '').includes('json');
  const data = isJson ? await r.json() : null;
  if (!r.ok) {
    const pesan = (data && data.error) || ('Gagal (' + r.status + ')');
    if (!silent) toast(pesan, 'err');
    const e = new Error(pesan);
    e.status = r.status;
    e.data = data;
    throw e;
  }
  return data;
}

async function unduhFile(url, namaCadangan) {
  const r = await fetch(url, { credentials: 'same-origin' });
  if (!r.ok) {
    let pesan = 'Gagal mengunduh (' + r.status + ')';
    try { const j = await r.json(); pesan = j.error || pesan; } catch (e) { /* bukan json */ }
    toast(pesan, 'err');
    return;
  }
  const blob = await r.blob();
  const cd = r.headers.get('Content-Disposition') || '';
  const m = /filename="?([^"]+)"?/.exec(cd);
  const nama = (m && m[1]) || namaCadangan || 'laporan';
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = nama;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  toast('File diunduh: ' + nama);
}

/* ---------------- Kamera selfie ---------------- */
function ambilFoto({ judul = 'Ambil Foto Selfie', keterangan = 'Wajah harus terlihat jelas. Foto dipakai sebagai bukti absensi.' } = {}) {
  return new Promise(async res => {
    let stream = null, mode = 'kamera';
    const box = el('div');
    box.innerHTML =
      '<div class="cam-wrap" id="camwrap"><div class="ph">Menyalakan kamera…</div></div>' +
      '<div class="cam-note">' + svg('info', 16) + '<span>' + esc(keterangan) + '</span></div>' +
      '<div class="inline" style="margin-top:12px;justify-content:center" id="camctrl"></div>';
    const m = bukaModal({
      judul,
      isi: box,
      aksi: '<button class="btn ghost" data-batal>Batal</button><button class="btn" data-kirim disabled>Simpan Absensi</button>',
    });
    const wrap = $('#camwrap', m), ctrl = $('#camctrl', m);
    const bKirim = $('[data-kirim]', m);
    let hasil = null;

    function tataKontrol(kameraAktif) {
      ctrl.innerHTML = '';
      if (kameraAktif) {
        const b = el('button', { className: 'btn', innerHTML: svg('camera', 18) + 'Ambil Foto' });
        b.onclick = jepret;
        ctrl.appendChild(b);
      }
      if (hasil) {
        const u = el('button', { className: 'btn ghost', innerHTML: svg('camera', 18) + 'Ulangi' });
        u.onclick = () => { hasil = null; bKirim.disabled = true; mulaiKamera(); };
        ctrl.appendChild(u);
      }
    }

    async function mulaiKamera() {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        return modeBerkas('Browser tidak mengizinkan akses kamera langsung (butuh http://localhost atau https).');
      }
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: { ideal: 720 }, height: { ideal: 540 } }, audio: false });
      } catch (e) {
        return modeBerkas('Kamera tidak bisa dibuka (' + (e.name || e.message) + '). Periksa izin kamera pada browser.');
      }
      wrap.innerHTML = '<video autoplay playsinline muted></video>';
      const v = $('video', wrap);
      v.srcObject = stream;
      // Tombol diaktifkan lebih dulu: pada sebagian perangkat play() baru selesai
      // setelah frame pertama tiba, dan menunggunya membuat tombol tidak pernah muncul.
      tataKontrol(true);
      v.play().catch(() => {});
      setTimeout(() => {
        if (!v.videoWidth && wrap.contains(v) && ctrl && !ctrl.querySelector('[data-berkas]')) {
          const b = el('button', { className: 'btn ghost', innerHTML: svg('camera', 18) + 'Pakai Kamera Perangkat' });
          b.dataset.berkas = '1';
          b.onclick = () => modeBerkas('Kamera langsung belum mengirim gambar.');
          ctrl.appendChild(b);
        }
      }, 4000);
    }

    function modeBerkas(alasan) {
      mode = 'berkas';
      stopStream();
      wrap.innerHTML = '<div class="ph">' + esc(alasan) + '<br><br>Gunakan tombol di bawah untuk memilih foto dari kamera perangkat.</div>';
      ctrl.innerHTML = '';
      const inp = el('input', { type: 'file', accept: 'image/*', capture: 'user', style: 'display:none' });
      const b = el('button', { className: 'btn', innerHTML: svg('camera', 18) + 'Buka Kamera Perangkat' });
      b.onclick = () => inp.click();
      inp.onchange = () => { if (inp.files[0]) berkasKeDataURL(inp.files[0]); };
      ctrl.appendChild(b);
      ctrl.appendChild(inp);
    }

    function berkasKeDataURL(file) {
      if (file.size > 6 * 1024 * 1024) return toast('Ukuran foto maksimal 6 MB.', 'err');
      const fr = new FileReader();
      fr.onload = () => { hasil = fr.result; wrap.innerHTML = '<img src="' + hasil + '" alt="Foto absensi">'; bKirim.disabled = false; tataKontrol(false); };
      fr.readAsDataURL(file);
    }

    function jepret() {
      const v = $('video', wrap);
      if (!v || !v.videoWidth) return toast('Kamera belum siap, coba lagi sesaat.', 'err');
      const skala = Math.min(1, 720 / v.videoWidth);
      const c = el('canvas', { width: Math.round(v.videoWidth * skala), height: Math.round(v.videoHeight * skala) });
      c.getContext('2d').drawImage(v, 0, 0, c.width, c.height);
      hasil = c.toDataURL('image/jpeg', 0.72);
      stopStream();
      wrap.innerHTML = '<img src="' + hasil + '" alt="Foto absensi">';
      bKirim.disabled = false;
      tataKontrol(false);
    }

    function stopStream() {
      if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null; }
    }

    m.addEventListener('click', e => {
      if (e.target.closest('[data-batal]') || e.target.closest('[data-close]')) { stopStream(); res(null); }
      if (e.target.closest('[data-kirim]')) { stopStream(); tutupModal(); res(hasil); }
    });
    // tutup lewat tombol Escape / klik mask
    const obs = new MutationObserver(() => { if (!document.body.contains(m)) { stopStream(); obs.disconnect(); } });
    obs.observe(document.body, { childList: true });

    if (mode === 'kamera') mulaiKamera();
  });
}

/* ---------------- Util lain ---------------- */
function unduhCSV(nama, baris) {
  const isi = baris.map(r => r.map(c => '"' + String(c == null ? '' : c).replace(/"/g, '""') + '"').join(',')).join('\r\n');
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob(['\ufeff' + isi], { type: 'text/csv;charset=utf-8;' }));
  a.download = nama;
  document.body.appendChild(a); a.click(); a.remove();
  toast('File diunduh: ' + nama);
}
const pbar = (persen, ok) => '<div class="pbar' + (persen >= 100 ? ' ok' : '') + '"><i style="width:' + Math.min(100, persen) + '%"></i></div>';
function jamDigital(node) {
  const tick = () => {
    const d = new Date();
    node.innerHTML = '<b>' + pad2(d.getHours()) + ':' + pad2(d.getMinutes()) + ':' + pad2(d.getSeconds()) + '</b>' +
      '<small>' + HARI[d.getDay()] + ', ' + d.getDate() + ' ' + BULAN[d.getMonth()] + ' ' + d.getFullYear() + '</small>';
  };
  tick();
  return setInterval(tick, 1000);
}
async function mulaiSesi(target) {
  const me = await api('/api/me', { silent: true });
  STATE.user = me.user;
  STATE.csrf = me.csrf;
  STATE.settings = me.settings;
  if (target && STATE.user.role !== target) { location.href = STATE.user.role === 'admin' ? '/admin' : '/karyawan'; return false; }
  return true;
}
async function keluar() {
  if (!(await konfirmasi('Keluar dari aplikasi sekarang?', { judul: 'Logout', tombol: 'Ya, keluar' }))) return;
  try { await api('/api/logout', { method: 'POST' }); } catch (e) { /* lanjut saja */ }
  location.href = '/';
}
