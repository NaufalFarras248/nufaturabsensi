"""
report.py — Export laporan tanpa dependensi eksternal.
  * write_xlsx() : file .xlsx asli (Office Open XML, ditulis manual via zipfile)
  * write_pdf()  : file .pdf asli (PDF 1.4, font Helvetica standar)
Keduanya hanya memakai stdlib Python.
"""
import io
import re
import zipfile


# ============================================================ XLSX
def _esc(s):
    s = '' if s is None else str(s)
    return (s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
             .replace('"', '&quot;').replace("'", '&apos;'))


def _kolom_letter(i):
    s = ''
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def _autofilter(baris, kolom):
    """Baris judul ikut bisa difilter + panah dropdown di Excel."""
    if not baris or not kolom:
        return ''
    n_kolom = max(len(r) for r in baris)
    return '<autoFilter ref="A1:%s%d"/>' % (_kolom_letter(n_kolom - 1), len(baris))


def _sheet_xml(sheet):
    kolom = sheet.get('kolom') or []
    baris = sheet.get('baris') or []
    cols = ''
    if kolom:
        parts = []
        for i, c in enumerate(kolom):
            lebar = c.get('lebar') if isinstance(c, dict) else None
            parts.append('<col min="%d" max="%d" width="%.2f" customWidth="1"/>' % (i + 1, i + 1, lebar or 18))
        cols = '<cols>%s</cols>' % ''.join(parts)
    rows = []
    # judul baris tebal (style 1)
    for r, row in enumerate(baris, start=1):
        cells = []
        for c, val in enumerate(row):
            ref = '%s%d' % (_kolom_letter(c), r)
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                # angka selalu style 2 (rata kanan, vertikal tengah)
                cells.append('<c r="%s" s="2"><v>%s</v></c>' % (ref, val))
            else:
                cells.append('<c r="%s" t="inlineStr" s="%d"><is><t xml:space="preserve">%s</t></is></c>'
                             % (ref, 1 if r == 1 else 0, _esc(val)))
        tinggi = ' ht="24" customHeight="1"' if r == 1 else ''
        rows.append('<row r="%d"%s>%s</row>' % (r, tinggi, ''.join(cells)))
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
            '%s%s<sheetData>%s</sheetData></worksheet>' % (cols, _autofilter(baris, kolom), ''.join(rows)))


def _styles_xml():
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<fonts count="3">'
            '<font><sz val="11"/><name val="Calibri"/></font>'
            '<font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>'
            '<font><sz val="11"/><name val="Calibri"/></font>'
            '</fonts>'
            '<fills count="3"><fill><patternFill patternType="none"/></fill>'
            '<fill><patternFill patternType="gray125"/></fill>'
            '<fill><patternFill patternType="solid"><fgColor rgb="FF1E293B"/><bgColor indexed="64"/></patternFill></fill></fills>'
            '<borders count="2"><border/><border><left style="thin"><color rgb="FF94A3B8"/></left>'
            '<right style="thin"><color rgb="FF94A3B8"/></right><top style="thin"><color rgb="FF94A3B8"/></top>'
            '<bottom style="thin"><color rgb="FF94A3B8"/></bottom></border></borders>'
            '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
            '<cellXfs count="3">'
            '<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1"/>'
            '<xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment vertical="center"/></xf>'
            '<xf numFmtId="0" fontId="2" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1"><alignment horizontal="right" vertical="center"/></xf>'
            '</cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')


def write_xlsx(path, sheets):
    """sheets: [{'nama': str, 'kolom': [{'lebar': 20}], 'baris': [[...]]}]"""
    if isinstance(sheets, dict):
        sheets = [sheets]
    konten = {
        '[Content_Types].xml': (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '%s'
            '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            '</Types>' % ''.join(
                '<Override PartName="/xl/worksheets/sheet%d.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' % (i + 1)
                for i in range(len(sheets)))),
        '_rels/.rels': (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>'),
        'xl/workbook.xml': (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
            '%s</sheets></workbook>' % ''.join(
                '<sheet name="%s" sheetId="%d" r:id="rId%d"/>' % (_esc(s.get('nama', 'Sheet%d' % (i + 1)))[:31], i + 1, i + 1)
                for i, s in enumerate(sheets))),
        'xl/_rels/workbook.xml.rels': (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '%s'
            '<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            '</Relationships>' % (
                ''.join('<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet%d.xml"/>' % (i + 1, i + 1)
                        for i in range(len(sheets))), len(sheets) + 1)),
        'xl/styles.xml': _styles_xml(),
    }
    for i, s in enumerate(sheets):
        konten['xl/worksheets/sheet%d.xml' % (i + 1)] = _sheet_xml(s)

    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        for nama, isi in konten.items():
            z.writestr(nama, isi)
    return path


# ============================================================ PDF
def _pdf_escape(s):
    return (str('' if s is None else s).replace('\\', r'\\').replace('(', r'\(').replace(')', r'\)')
            .encode('latin-1', 'replace').decode('latin-1'))


def _lebar_teks(s, ukuran=8):
    """Perkiraan lebar Helvetica (koefisien rata-rata 0.5 em, cukup untuk tabel laporan)."""
    return len(str('' if s is None else s)) * ukuran * 0.5


def _potong(s, maks, ukuran=8):
    s = str('' if s is None else s)
    if _lebar_teks(s, ukuran) <= maks:
        return s
    n = max(1, int(maks / (ukuran * 0.5)) - 1)
    return s[:n] + '…'


def _angka(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def write_pdf(path, judul, kolom, baris, lebar_kolom=None, landscape=True, subjudul=''):
    """Tabel laporan A4. kolom: [str], baris: [[...]], lebar_kolom: [float] dalam poin."""
    W, H = (841.89, 595.28) if landscape else (595.28, 841.89)
    margin = 32
    ukuran = 8
    baris_tinggi = 14
    max_baris_per_halaman = int((H - margin - 110) / baris_tinggi)
    n = len(kolom)
    total = sum(lebar_kolom) if lebar_kolom else (W - 2 * margin)
    lebar = lebar_kolom or [(W - 2 * margin) / n] * n
    skala = (W - 2 * margin) / total if total else 1
    lebar = [w * skala for w in lebar]

    # kolom yang isinya angka -> rata kanan
    rata_kanan = []
    for i in range(n):
        vals = [row[i] for row in baris if len(row) > i and str(row[i]).strip() != '']
        rata_kanan.append(bool(vals) and all(_angka(v) for v in vals))

    halaman = [baris[i:i + max_baris_per_halaman] for i in range(0, len(baris), max_baris_per_halaman)] or [[]]

    objs = []          # (nomor objek -> isi)
    stream_ids = []
    page_ids = []

    def teks(x, y, s, ukuran=8, font='F1', warna=None):
        w = '' if warna is None else str(warna) + ' rg '
        return 'BT /%s %d Tf %s1 0 0 1 %.2f %.2f Tm (%s) Tj ET\n' % (font, ukuran, w, x, y, _pdf_escape(s))

    for idx, blok in enumerate(halaman):
        c = []
        c.append('0.118 0.161 0.231 rg 0 %d %d 58 re f\n' % (H - 58, W))
        c.append(teks(margin, H - 26, judul, 13, 'F2', '1 1 1'))
        info = subjudul or ''
        info += '   |   Dicetak: %s' % __import__('datetime').datetime.now().strftime('%d/%m/%Y %H:%M')
        c.append(teks(margin, H - 44, info, 8, 'F1', '0.85 0.88 0.93'))
        y = H - 80
        # header tabel
        c.append('0.902 0.925 0.945 rg 0 %.2f %d %.2f re f\n' % (y - 4, W, baris_tinggi))
        x = margin
        for i, k in enumerate(kolom):
            label = _potong(k, lebar[i] - 6, ukuran)
            xt = x + 3
            if rata_kanan[i]:
                xt = x + lebar[i] - 3 - _lebar_teks(label, ukuran)
            c.append(teks(xt, y, label, ukuran, 'F2'))
            x += lebar[i]
        y -= baris_tinggi
        if not blok:
            c.append(teks(margin + 3, y, 'Tidak ada data pada periode ini.', ukuran, 'F1', '0.42 0.47 0.53'))
            y -= baris_tinggi
        for r, row in enumerate(blok):
            if r % 2 == 1:
                c.append('0.965 0.973 0.980 rg 0 %.2f %d %.2f re f\n' % (y - 3, W, baris_tinggi))
            x = margin
            for i, val in enumerate(row[:n]):
                s = val
                if isinstance(val, float):
                    s = ('%.2f' % val).rstrip('0').rstrip('.')
                t = _potong(s, lebar[i] - 6, ukuran)
                xt = x + 3
                if rata_kanan[i]:
                    xt = x + lebar[i] - 3 - _lebar_teks(t, ukuran)
                c.append(teks(xt, y, t, ukuran))
                x += lebar[i]
            c.append('0.80 0.84 0.88 RG 0.4 w %d %.2f m %d %.2f l S\n' % (margin, y - 4, W - margin, y - 4))
            y -= baris_tinggi
        c.append('%d %.2f m %d %.2f l S\n' % (margin, y + baris_tinggi - 4, W - margin, y + baris_tinggi - 4))
        c.append(teks(margin, 20, '%s — halaman %d dari %d' % (judul, idx + 1, len(halaman)), 7))
        c.append(teks(W - margin - 90, 20, 'Total baris: %d' % len(baris), 7))
        stream = ''.join(c).encode('latin-1', 'replace')
        stream_ids.append(stream)
        page_ids.append(None)

    # susun objek PDF: 1=Catalog, 2=Pages, lalu tiap halaman (Page, Contents), terakhir Font
    total_hal = len(stream_ids)
    n_obj = 2 + total_hal * 2 + 2
    page_obj_ids = [3 + i * 2 for i in range(total_hal)]
    font1 = n_obj - 1
    font2 = n_obj
    out = io.BytesIO()
    out.write(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
    offsets = {}

    def obj(num, isi):
        offsets[num] = out.tell()
        if isinstance(isi, str):
            isi = isi.encode('latin-1', 'replace')
        out.write(b'%d 0 obj\n' % num + isi + b'\nendobj\n')

    obj(1, '<< /Type /Catalog /Pages 2 0 R >>')
    obj(2, '<< /Type /Pages /Count %d /Kids [%s] >>' % (total_hal, ' '.join('%d 0 R' % p for p in page_obj_ids)))
    for i, (pid, stream) in enumerate(zip(page_obj_ids, stream_ids)):
        cid = pid + 1
        obj(pid, '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %.2f %.2f] /Resources << /Font << /F1 %d 0 R /F2 %d 0 R >> >> /Contents %d 0 R >>'
            % (W, H, font1, font2, cid))
        obj(cid, b'<< /Length %d >>\nstream\n' % len(stream) + stream + b'endstream')
    obj(font1, '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>')
    obj(font2, '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>')

    xref = out.tell()
    out.write(b'xref\n0 %d\n' % (n_obj + 1))
    out.write(b'0000000000 65535 f \n')
    for i in range(1, n_obj + 1):
        out.write(b'%010d 00000 n \n' % offsets.get(i, 0))
    out.write(b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (n_obj + 1, xref))

    with open(path, 'wb') as f:
        f.write(out.getvalue())
    return path
