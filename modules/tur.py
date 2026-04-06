"""
modules/tur.py  —  Tur Yönetimi
3 sekme:
  1. Tura Çıkış   — barkod VEYA listeden arama ile yükle
  2. Turdan Dönüş — barkod VEYA listeden dönüş al, fark stoktan düş
  3. Tur Programı — haftalık liste, yeni tur ekle
"""
import os
from datetime import datetime, date
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QSplitter,
    QPushButton, QLabel, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFrame, QComboBox, QTextEdit,
    QMessageBox, QDialog, QDateEdit, QSpinBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QDate, QTimer, QThread
from PyQt6.QtGui import QColor, QFont

from core.database import get_conn, barkod_coz
from core.tema import RENK
from core.widgets import StatKart, AyiriciCizgi
from core.sheets import get_sheets


# ── Sheets arka plan thread'i ─────────────────────────────────────────────────
class _SheetsCallThread(QThread):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn = fn; self._args = args; self._kwargs = kwargs
    def run(self):
        try: self._fn(*self._args, **self._kwargs)
        except Exception: pass


# ── Barkod giriş kutusu ───────────────────────────────────────────────────
class BarkodInput(QLineEdit):
    barkod_okundu = pyqtSignal(str)
    def __init__(self, ph="Barkod okutun (örn: 99-1) veya ID..."):
        super().__init__()
        self.setPlaceholderText(ph)
        self.setMinimumHeight(46)
        self.setStyleSheet(f"""QLineEdit{{
            font-size:17px; font-weight:700;
            border:2px solid {RENK['cizgi_koyu']}; border-radius:8px;
            padding:8px 14px; background:{RENK['yuzey']}; color:{RENK['metin']};
        }}QLineEdit:focus{{border-color:{RENK['metin']};}}""")
        self.returnPressed.connect(self._emit)
    def _emit(self):
        val = self.text().strip()
        if val: self.barkod_okundu.emit(val); self.clear()


# ── Arama paneli (tur çıkış/dönüş ortak) ─────────────────────────────────
class UrunAramaPaneli(QWidget):
    """Metin aramasıyla stok_birimi seçimi — barkod alternatifi."""
    secildi = pyqtSignal(dict)   # seçilen birim bilgisi

    def __init__(self, sadece_depoda=True):
        super().__init__()
        self.sadece_depoda = sadece_depoda
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0,0,0,0); lay.setSpacing(6)

        fil = QHBoxLayout()
        self.ara = QLineEdit(); self.ara.setPlaceholderText("Marka, model veya referans ara...")
        self.ara.setMinimumHeight(36); self.ara.textChanged.connect(self._ara)
        self.cb_kat = QComboBox(); self.cb_kat.setMinimumHeight(36)
        self.cb_kat.addItems(["Tümü","Beyin","ABS","Plastik"])
        self.cb_kat.currentIndexChanged.connect(self._ara)
        fil.addWidget(self.ara, 3); fil.addWidget(self.cb_kat, 1)
        lay.addLayout(fil)

        self.tablo = QTableWidget()
        self.tablo.setColumnCount(6)
        self.tablo.setHorizontalHeaderLabels(
            ["BARKOD ID","KATEGORİ","MARKA","YAYGIN AD","DURUM","REF 1"])
        self.tablo.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tablo.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tablo.verticalHeader().setVisible(False)
        self.tablo.setAlternatingRowColors(True)
        self.tablo.setMinimumHeight(160)
        hh = self.tablo.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tablo.verticalHeader().setDefaultSectionSize(28)
        self.tablo.doubleClicked.connect(self._sec)
        lay.addWidget(self.tablo)

        btn = QPushButton("+ Seçili Ürünü Ekle")
        btn.setObjectName("BtnIkincil"); btn.clicked.connect(self._sec)
        lay.addWidget(btn)
        self._ara()

    def _ara(self):
        ara = self.ara.text().strip().lower()
        kat = self.cb_kat.currentText()
        conn = get_conn()
        durum_filtre = "AND sb.durum='DEPODA'" if self.sadece_depoda else ""
        kat_filtre   = f"AND s.kategori='{kat}'" if kat != "Tümü" else ""
        rows = conn.execute(f"""
            SELECT sb.id as birim_id, sb.barkod_id, sb.durum,
                   s.id as stok_id, s.kategori, s.marka, s.yaygin_ad,
                   s.ref1, s.ref2, s.fiyat
            FROM stok_birimi sb JOIN stok s ON s.id=sb.stok_id
            WHERE 1=1 {durum_filtre} {kat_filtre}
            ORDER BY s.marka, s.yaygin_ad, sb.barkod_id
            LIMIT 200
        """).fetchall()
        conn.close()

        if ara:
            rows = [r for r in rows if ara in (
                (r["marka"] or "") + " " + (r["yaygin_ad"] or "") + " " +
                (r["ref1"] or "") + " " + (r["ref2"] or "") + " " +
                (r["barkod_id"] or "")
            ).lower()]

        self.tablo.setRowCount(len(rows))
        self._rows = [dict(r) for r in rows]
        durum_renk = {"DEPODA": RENK["yesil"], "TURDA": RENK["mavi"],
                      "SATILDI": RENK["metin3"]}
        for i, r in enumerate(self._rows):
            vals = [r["barkod_id"], r["kategori"], r["marka"],
                    r["yaygin_ad"], r["durum"], r.get("ref1","-") or "-"]
            for j, val in enumerate(vals):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                if j == 4:
                    item.setForeground(QColor(durum_renk.get(r["durum"], RENK["metin"])))
                    item.setFont(QFont("", -1, QFont.Weight.Bold))
                self.tablo.setItem(i, j, item)

    def _sec(self):
        rows = self.tablo.selectionModel().selectedRows()
        if not rows: return
        self.secildi.emit(self._rows[rows[0].row()])


# ══════════════════════════════════════════════════════════════════════════
#  1. TURA ÇIKIŞ
# ══════════════════════════════════════════════════════════════════════════
class TuraCikisSayfasi(QWidget):
    def __init__(self):
        super().__init__()
        self._tur_id  = None
        self._tur_adi = ""
        self._yuklu   = set()   # yüklenen birim_id'ler
        self._build()
        self._turleri_yukle()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20,16,20,16); lay.setSpacing(12)

        # Tur seçici
        tur_lay = QHBoxLayout()
        lbl = QLabel("Aktif Tur:")
        lbl.setStyleSheet(f"font-weight:700; color:{RENK['metin2']}; font-size:12px;")
        self.cb_tur = QComboBox(); self.cb_tur.setMinimumHeight(40); self.cb_tur.setMinimumWidth(300)
        self.cb_tur.currentIndexChanged.connect(self._tur_secildi)
        self.lbl_durum = QLabel("")
        self.lbl_durum.setStyleSheet(f"color:{RENK['metin2']}; font-size:12px;")
        tur_lay.addWidget(lbl); tur_lay.addWidget(self.cb_tur)
        tur_lay.addWidget(self.lbl_durum); tur_lay.addStretch()
        lay.addLayout(tur_lay)
        lay.addWidget(AyiriciCizgi())

        # Stat kartları
        stat = QHBoxLayout(); stat.setSpacing(12)
        self.s_yuklu  = StatKart("Bu Turda Yüklü", "0", RENK["mavi"])
        self.s_toplam = StatKart("Toplam Taranan",  "0", RENK["metin2"])
        stat.addWidget(self.s_yuklu); stat.addWidget(self.s_toplam); stat.addStretch()
        lay.addLayout(stat)

        # Dikey splitter: üst = barkod+arama, alt = yüklü ürünler
        vsplit = QSplitter(Qt.Orientation.Vertical)

        # ── Üst panel: barkod girişi ve listeden seçim ───────────────────
        ust_w = QWidget()
        ust_lay = QVBoxLayout(ust_w); ust_lay.setContentsMargins(0,0,0,4); ust_lay.setSpacing(8)

        hsplit = QSplitter(Qt.Orientation.Horizontal)

        # Sol: Barkod girişi
        sol = QWidget()
        sl = QVBoxLayout(sol); sl.setContentsMargins(0,0,8,0); sl.setSpacing(8)
        kart = QFrame(); kart.setObjectName("Kart")
        kart.setStyleSheet(f"QFrame#Kart{{background:{RENK['yuzey']};border-radius:10px;"
                           f"border:1px solid {RENK['cizgi']};}}")
        kl = QVBoxLayout(kart); kl.setContentsMargins(14,12,14,12); kl.setSpacing(8)
        lbl2 = QLabel("BARKOD / ID OKUT")
        lbl2.setStyleSheet(f"font-size:10px; font-weight:700; letter-spacing:2px; color:{RENK['metin2']};")
        kl.addWidget(lbl2)
        self.barkod_in = BarkodInput()
        self.barkod_in.barkod_okundu.connect(self._isle)
        kl.addWidget(self.barkod_in)
        self.lbl_flash = QLabel("")
        self.lbl_flash.setStyleSheet("font-size:12px; font-weight:700;")
        kl.addWidget(self.lbl_flash)
        kl.addStretch()
        sl.addWidget(kart)
        hsplit.addWidget(sol)

        # Sağ: Arama ile seç
        sag = QWidget()
        sagl = QVBoxLayout(sag); sagl.setContentsMargins(8,0,0,0); sagl.setSpacing(8)
        lbl3 = QLabel("VEYA LİSTEDEN SEÇ")
        lbl3.setStyleSheet(f"font-size:10px; font-weight:700; letter-spacing:2px; color:{RENK['metin2']};")
        sagl.addWidget(lbl3)
        self.arama = UrunAramaPaneli(sadece_depoda=True)
        self.arama.secildi.connect(self._listeden_isle)
        sagl.addWidget(self.arama, 1)
        hsplit.addWidget(sag)
        hsplit.setSizes([320, 580])
        ust_lay.addWidget(hsplit, 1)
        vsplit.addWidget(ust_w)

        # ── Alt panel: yüklü ürünler ─────────────────────────────────────
        alt_w = QWidget()
        alt_lay = QVBoxLayout(alt_w); alt_lay.setContentsMargins(0,4,0,0); alt_lay.setSpacing(6)

        lbl4 = QLabel("BU TURDA YÜKLÜ ÜRÜNLER")
        lbl4.setStyleSheet(f"font-size:10px; font-weight:700; letter-spacing:2px; color:{RENK['metin2']};")
        alt_lay.addWidget(lbl4)

        self.tablo = QTableWidget()
        self.tablo.setColumnCount(6)
        self.tablo.setHorizontalHeaderLabels(
            ["BARKOD ID","KATEGORİ","MARKA","YAYGIN AD","YÜKLEME ZAMANI","SHEETS"])
        self.tablo.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tablo.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tablo.verticalHeader().setVisible(False)
        self.tablo.setAlternatingRowColors(True)
        hh = self.tablo.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.tablo.verticalHeader().setDefaultSectionSize(30)
        alt_lay.addWidget(self.tablo, 1)

        btn_sil_lay = QHBoxLayout()
        btn_sil = QPushButton("Seçili Kaydı Kaldır"); btn_sil.setObjectName("BtnTehlike")
        btn_sil.clicked.connect(self._kaldir)
        btn_sil_lay.addWidget(btn_sil); btn_sil_lay.addStretch()
        alt_lay.addLayout(btn_sil_lay)
        vsplit.addWidget(alt_w)

        vsplit.setSizes([320, 380])
        lay.addWidget(vsplit, 1)

    def _turleri_yukle(self):
        self.cb_tur.blockSignals(True); self.cb_tur.clear()
        self.cb_tur.addItem("— Tur seçin —", None)
        conn = get_conn()
        turlar = conn.execute(
            "SELECT id,tur_adi,durum FROM tur WHERE durum!='TAMAMLANDI' ORDER BY olusturma DESC"
        ).fetchall()
        conn.close()
        for t in turlar:
            self.cb_tur.addItem(f"{t['tur_adi']}  [{t['durum']}]", t["id"])
        self.cb_tur.blockSignals(False)

    def _tur_secildi(self, _):
        self._tur_id  = self.cb_tur.currentData()
        self._tur_adi = self.cb_tur.currentText().split("[")[0].strip()
        self._yuklu   = set()
        if self._tur_id:
            conn = get_conn()
            rows = conn.execute(
                "SELECT birim_id FROM tur_urun WHERE tur_id=? AND birim_id IS NOT NULL",
                (self._tur_id,)).fetchall()
            conn.close()
            self._yuklu = {r["birim_id"] for r in rows}
            self.lbl_durum.setText(f"{len(self._yuklu)} yüklü")
        else:
            self.lbl_durum.setText("")
        self._tabloyu_yenile()

    def _isle(self, barkod_str):
        """Barkod okuyucudan gelen değeri işle."""
        if not self._tur_id:
            self._flash("⚠ Önce tur seçin!", RENK["aksan"]); return
        bilgi = barkod_coz(barkod_str)
        if not bilgi:
            self._flash(f"✗ '{barkod_str}' bulunamadı!", RENK["aksan"]); return
        # barkod_coz stok_birimi döndürüyorsa birim_id var
        birim_id = bilgi.get("id") or bilgi.get("birim_id")
        if not birim_id:
            self._flash(f"✗ Birim bulunamadı!", RENK["aksan"]); return
        durum = bilgi.get("durum", "")
        if durum == "TURDA" and birim_id in self._yuklu:
            self._flash(f"⚠ {barkod_str} zaten yüklü!", RENK["sari"]); return
        if durum == "SATILDI":
            self._flash(f"⚠ Bu ürün satılmış!", RENK["aksan"]); return
        self._yukle(birim_id, bilgi, barkod_str)

    def _listeden_isle(self, bilgi: dict):
        """Listeden seçilen birimi yükle."""
        if not self._tur_id:
            self._flash("⚠ Önce tur seçin!", RENK["aksan"]); return
        birim_id = bilgi.get("birim_id") or bilgi.get("id")
        if birim_id in self._yuklu:
            self._flash(f"⚠ {bilgi['barkod_id']} zaten yüklü!", RENK["sari"]); return
        self._yukle(birim_id, bilgi, bilgi["barkod_id"])

    def _yukle(self, birim_id, bilgi, barkod_str):
        conn = get_conn()
        stok_id = bilgi.get("stok_id") or bilgi.get("id")
        conn.execute(
            "INSERT INTO tur_urun (tur_id,stok_id,birim_id,barkod_id,cikis_zamani,durum) "
            "VALUES (?,?,?,?,datetime('now','localtime'),'YUKLU')",
            (self._tur_id, stok_id, birim_id, barkod_str))
        conn.execute(
            "UPDATE stok_birimi SET durum='TURDA', tur_id=? WHERE id=?",
            (self._tur_id, birim_id))
        conn.commit(); conn.close()
        self._yuklu.add(birim_id)

        sheets = get_sheets()
        if sheets.aktif:
            t = _SheetsCallThread(
                sheets.tura_cikis_ekle,
                self._tur_adi, stok_id,
                bilgi.get("kategori",""), bilgi.get("marka",""),
                bilgi.get("yaygin_ad",""), bilgi.get("ref1",""), barkod_str)
            t.finished.connect(t.deleteLater); t.start()
        self._flash(f"✓ {bilgi.get('marka','')} / {bilgi.get('yaygin_ad','')} — yüklendi",
                    RENK["yesil"])
        self._tabloyu_yenile()
        self.arama._ara()   # arama listesini güncelle

    def _tabloyu_yenile(self):
        if not self._tur_id:
            self.tablo.setRowCount(0)
            self.s_yuklu.set_deger(0); self.s_toplam.set_deger(0); return
        conn = get_conn()
        rows = conn.execute("""
            SELECT tu.barkod_id, tu.cikis_zamani,
                   s.kategori, s.marka, s.yaygin_ad
            FROM tur_urun tu JOIN stok s ON s.id=tu.stok_id
            WHERE tu.tur_id=? ORDER BY tu.id DESC
        """, (self._tur_id,)).fetchall()
        conn.close()
        sheets_ok = get_sheets().aktif
        self.tablo.setRowCount(len(rows))
        for i, r in enumerate(rows):
            vals = [r["barkod_id"] or "-", r["kategori"], r["marka"],
                    r["yaygin_ad"], str(r["cikis_zamani"] or "")[:16],
                    "✓" if sheets_ok else "—"]
            for j, val in enumerate(vals):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                if j == 5:
                    item.setForeground(QColor(RENK["yesil"] if sheets_ok else RENK["metin3"]))
                self.tablo.setItem(i, j, item)
        n = len(rows)
        self.s_yuklu.set_deger(n); self.s_toplam.set_deger(n)

    def _kaldir(self):
        rows = self.tablo.selectionModel().selectedRows()
        if not rows or not self._tur_id: return
        barkod = self.tablo.item(rows[0].row(), 0).text()
        conn = get_conn()
        birim = conn.execute(
            "SELECT id FROM stok_birimi WHERE barkod_id=?", (barkod,)).fetchone()
        if birim:
            conn.execute("UPDATE stok_birimi SET durum='DEPODA', tur_id=NULL WHERE id=?",
                         (birim["id"],))
            self._yuklu.discard(birim["id"])
        conn.execute("DELETE FROM tur_urun WHERE tur_id=? AND barkod_id=?",
                     (self._tur_id, barkod))
        conn.commit(); conn.close()
        self._tabloyu_yenile(); self.arama._ara()

    def _flash(self, m, r):
        self.lbl_flash.setText(m)
        self.lbl_flash.setStyleSheet(f"font-size:12px; font-weight:700; color:{r};")
        QTimer.singleShot(3000, lambda: self.lbl_flash.setText(""))

    def guncelle(self):
        self._turleri_yukle()


# ══════════════════════════════════════════════════════════════════════════
#  2. TURDAN DÖNÜŞ
# ══════════════════════════════════════════════════════════════════════════
class TurDonusSayfasi(QWidget):
    def __init__(self):
        super().__init__()
        self._tur_id   = None
        self._tur_adi  = ""
        self._cikanlar = {}   # birim_id → bilgi
        self._donen    = set()
        self._build()
        self._turleri_yukle()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20,16,20,16); lay.setSpacing(12)

        tur_lay = QHBoxLayout()
        lbl = QLabel("Tur:")
        lbl.setStyleSheet(f"font-weight:700; color:{RENK['metin2']}; font-size:12px;")
        self.cb_tur = QComboBox(); self.cb_tur.setMinimumHeight(40); self.cb_tur.setMinimumWidth(300)
        self.cb_tur.currentIndexChanged.connect(self._tur_secildi)
        tur_lay.addWidget(lbl); tur_lay.addWidget(self.cb_tur); tur_lay.addStretch()
        lay.addLayout(tur_lay); lay.addWidget(AyiriciCizgi())

        stat = QHBoxLayout(); stat.setSpacing(12)
        self.s_cikan  = StatKart("Tura Çıkan",   "0", RENK["mavi"])
        self.s_donen  = StatKart("Dönen",         "0", RENK["yesil"])
        self.s_eksik  = StatKart("Satılan/Eksik", "0", RENK["aksan"])
        for s in [self.s_cikan, self.s_donen, self.s_eksik]:
            stat.addWidget(s)
        stat.addStretch(); lay.addLayout(stat)

        # Dikey splitter: üst = barkod+arama, alt = çıkan/dönen tablolar
        vsplit = QSplitter(Qt.Orientation.Vertical)

        # ── Üst panel: barkod girişi ve listeden seçim ───────────────────
        ust_w = QWidget()
        ust_lay = QVBoxLayout(ust_w); ust_lay.setContentsMargins(0,0,0,4); ust_lay.setSpacing(8)

        hsplit = QSplitter(Qt.Orientation.Horizontal)

        sol = QWidget()
        sl = QVBoxLayout(sol); sl.setContentsMargins(0,0,8,0); sl.setSpacing(8)
        kart = QFrame(); kart.setObjectName("Kart")
        kart.setStyleSheet(f"QFrame#Kart{{background:{RENK['yuzey']};border-radius:10px;"
                           f"border:1px solid {RENK['cizgi']};}}")
        kl = QVBoxLayout(kart); kl.setContentsMargins(14,12,14,12); kl.setSpacing(8)
        lbl2 = QLabel("ARAÇTAN İNİRKEN OKUT")
        lbl2.setStyleSheet(f"font-size:10px; font-weight:700; letter-spacing:2px; color:{RENK['metin2']};")
        kl.addWidget(lbl2)
        self.barkod_in = BarkodInput("Dönen ürün barkodunu okutun...")
        self.barkod_in.barkod_okundu.connect(self._isle)
        kl.addWidget(self.barkod_in)
        self.lbl_flash = QLabel("")
        self.lbl_flash.setStyleSheet("font-size:12px; font-weight:700;")
        kl.addWidget(self.lbl_flash)
        kl.addStretch()
        sl.addWidget(kart)
        hsplit.addWidget(sol)

        sag = QWidget()
        sagl = QVBoxLayout(sag); sagl.setContentsMargins(8,0,0,0); sagl.setSpacing(8)
        lbl3 = QLabel("VEYA TURDA OLANLARDAN SEÇ")
        lbl3.setStyleSheet(f"font-size:10px; font-weight:700; letter-spacing:2px; color:{RENK['metin2']};")
        sagl.addWidget(lbl3)
        self.arama = UrunAramaPaneli(sadece_depoda=False)
        self.arama.secildi.connect(self._listeden_isle)
        sagl.addWidget(self.arama, 1)
        hsplit.addWidget(sag)
        hsplit.setSizes([320, 580])
        ust_lay.addWidget(hsplit, 1)
        vsplit.addWidget(ust_w)

        # ── Alt panel: çıkan ve dönen tablolar ───────────────────────────
        alt_w = QWidget()
        alt_lay = QVBoxLayout(alt_w); alt_lay.setContentsMargins(0,4,0,0); alt_lay.setSpacing(8)

        tablo_lay = QHBoxLayout(); tablo_lay.setSpacing(12)

        sol2 = QWidget(); sl2 = QVBoxLayout(sol2); sl2.setContentsMargins(0,0,0,0)
        lbl_c = QLabel("TURA ÇIKAN")
        lbl_c.setStyleSheet(f"font-size:10px; font-weight:700; letter-spacing:2px; color:{RENK['mavi']};")
        sl2.addWidget(lbl_c)
        self.tablo_cikan = self._tablo_olustur(); sl2.addWidget(self.tablo_cikan)
        tablo_lay.addWidget(sol2)

        sag2 = QWidget(); sagl2 = QVBoxLayout(sag2); sagl2.setContentsMargins(0,0,0,0)
        lbl_d = QLabel("DÖNEN")
        lbl_d.setStyleSheet(f"font-size:10px; font-weight:700; letter-spacing:2px; color:{RENK['yesil']};")
        sagl2.addWidget(lbl_d)
        self.tablo_donen = self._tablo_olustur(); sagl2.addWidget(self.tablo_donen)
        tablo_lay.addWidget(sag2)
        alt_lay.addLayout(tablo_lay, 1)

        btn_lay = QHBoxLayout()
        btn_tam = QPushButton("✓  Turu Tamamla — Satılanları Stoktan Düş")
        btn_tam.setObjectName("BtnAksan"); btn_tam.clicked.connect(self._tamamla)
        btn_lay.addStretch(); btn_lay.addWidget(btn_tam)
        alt_lay.addLayout(btn_lay)
        vsplit.addWidget(alt_w)

        vsplit.setSizes([320, 380])
        lay.addWidget(vsplit, 1)

    def _tablo_olustur(self):
        t = QTableWidget(); t.setColumnCount(4)
        t.setHorizontalHeaderLabels(["BARKOD ID","KATEGORİ","MARKA","YAYGIN AD"])
        t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        t.verticalHeader().setVisible(False); t.setAlternatingRowColors(True)
        hh = t.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        t.verticalHeader().setDefaultSectionSize(28)
        return t

    def _turleri_yukle(self):
        self.cb_tur.blockSignals(True); self.cb_tur.clear()
        self.cb_tur.addItem("— Tur seçin —", None)
        conn = get_conn()
        turlar = conn.execute(
            "SELECT id,tur_adi,durum FROM tur ORDER BY olusturma DESC").fetchall()
        conn.close()
        for t in turlar:
            self.cb_tur.addItem(f"{t['tur_adi']}  [{t['durum']}]", t["id"])
        self.cb_tur.blockSignals(False)

    def _tur_secildi(self, _):
        self._tur_id  = self.cb_tur.currentData()
        self._tur_adi = self.cb_tur.currentText().split("[")[0].strip()
        self._donen   = set()
        if not self._tur_id:
            self._cikanlar = {}
            self.tablo_cikan.setRowCount(0); self.tablo_donen.setRowCount(0); return
        conn = get_conn()
        rows = conn.execute("""
            SELECT tu.birim_id, tu.barkod_id, tu.durum,
                   s.kategori, s.marka, s.yaygin_ad
            FROM tur_urun tu JOIN stok s ON s.id=tu.stok_id
            WHERE tu.tur_id=?
        """, (self._tur_id,)).fetchall()
        conn.close()
        self._cikanlar = {r["birim_id"]: dict(r) for r in rows if r["birim_id"]}
        self._donen    = {bid for bid, r in self._cikanlar.items()
                         if r["durum"] in ("IADE","SATILDI")}
        self._tablolari_yenile()

    def _isle(self, barkod_str):
        if not self._tur_id:
            self._flash("⚠ Önce tur seçin!", RENK["aksan"]); return
        bilgi = barkod_coz(barkod_str)
        if not bilgi:
            self._flash(f"✗ '{barkod_str}' bulunamadı!", RENK["aksan"]); return
        birim_id = bilgi.get("id") or bilgi.get("birim_id")
        if birim_id not in self._cikanlar:
            self._flash(f"⚠ Bu ürün bu turun listesinde değil!", RENK["sari"]); return
        if birim_id in self._donen:
            self._flash(f"⚠ Zaten tarandı!", RENK["sari"]); return
        self._donus_isle(birim_id, bilgi.get("marka",""), bilgi.get("yaygin_ad",""))

    def _listeden_isle(self, bilgi: dict):
        if not self._tur_id:
            self._flash("⚠ Önce tur seçin!", RENK["aksan"]); return
        birim_id = bilgi.get("birim_id") or bilgi.get("id")
        if birim_id not in self._cikanlar:
            self._flash("⚠ Bu ürün bu turun listesinde değil!", RENK["sari"]); return
        if birim_id in self._donen:
            self._flash("⚠ Zaten işaretlendi!", RENK["sari"]); return
        self._donus_isle(birim_id, bilgi.get("marka",""), bilgi.get("yaygin_ad",""))

    def _donus_isle(self, birim_id, marka, ad):
        conn = get_conn()
        conn.execute(
            "UPDATE tur_urun SET durum='IADE', donus_zamani=datetime('now','localtime') "
            "WHERE tur_id=? AND birim_id=?", (self._tur_id, birim_id))
        conn.execute(
            "UPDATE stok_birimi SET durum='DEPODA', tur_id=NULL WHERE id=?", (birim_id,))
        conn.commit(); conn.close()
        self._donen.add(birim_id)
        self._cikanlar[birim_id]["durum"] = "IADE"
        sheets = get_sheets()
        if sheets.aktif:
            r = self._cikanlar[birim_id]
            t = _SheetsCallThread(
                sheets.tur_donus_ekle,
                self._tur_adi, birim_id,
                r["kategori"], r["marka"], r["yaygin_ad"], "İADE")
            t.finished.connect(t.deleteLater); t.start()
        self._flash(f"✓ {marka} / {ad} — iade alındı", RENK["yesil"])
        self._tablolari_yenile(); self.arama._ara()

    def _tablolari_yenile(self):
        cikan = list(self._cikanlar.values())
        donen = [r for r in cikan if r["birim_id"] in self._donen]
        eksik = [r for r in cikan if r["birim_id"] not in self._donen]
        self.s_cikan.set_deger(len(cikan))
        self.s_donen.set_deger(len(donen))
        self.s_eksik.set_deger(len(eksik))

        def doldur(tablo, rows, renk=None):
            tablo.setRowCount(len(rows))
            for i, r in enumerate(rows):
                vals = [r.get("barkod_id","-"), r["kategori"], r["marka"], r["yaygin_ad"]]
                for j, val in enumerate(vals):
                    item = QTableWidgetItem(str(val))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                    if renk: item.setForeground(QColor(renk))
                    tablo.setItem(i, j, item)

        doldur(self.tablo_cikan, cikan)
        # Çıkan tabloda renk: dönen=yeşil, dönmeyen=kırmızı
        for i, r in enumerate(cikan):
            c = RENK["yesil"] if r["birim_id"] in self._donen else RENK["aksan"]
            for j in range(4):
                it = self.tablo_cikan.item(i, j)
                if it: it.setForeground(QColor(c))
        doldur(self.tablo_donen, donen, RENK["yesil"])

    def _tamamla(self):
        if not self._tur_id: return
        eksik = {bid: r for bid, r in self._cikanlar.items()
                 if bid not in self._donen}
        msg = (f"Tüm ürünler iade alındı.\nTuru kapatmak istiyor musunuz?" if not eksik
               else f"{len(eksik)} ürün geri gelmedi — stoktan düşülecek.\nDevam?")
        if QMessageBox.question(self, "Turu Tamamla", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            ) != QMessageBox.StandardButton.Yes: return

        conn = get_conn(); sheets = get_sheets()
        for bid, r in eksik.items():
            sid = None
            # stok_id'yi bul
            tu = conn.execute(
                "SELECT stok_id FROM tur_urun WHERE tur_id=? AND birim_id=?",
                (self._tur_id, bid)).fetchone()
            if tu: sid = tu["stok_id"]
            conn.execute(
                "UPDATE stok_birimi SET durum='SATILDI' WHERE id=?", (bid,))
            conn.execute(
                "UPDATE tur_urun SET durum='SATILDI', donus_zamani=datetime('now','localtime') "
                "WHERE tur_id=? AND birim_id=?", (self._tur_id, bid))
            if sid:
                conn.execute(
                    "UPDATE stok SET stok_miktari="
                    "(SELECT COUNT(*) FROM stok_birimi WHERE stok_id=? AND durum='DEPODA'),"
                    "guncelleme=datetime('now','localtime') WHERE id=?", (sid, sid))
            if sheets.aktif:
                t = _SheetsCallThread(
                    sheets.tur_donus_ekle, self._tur_adi, bid,
                    r["kategori"], r["marka"], r["yaygin_ad"],
                    "SATILDI", "Turdan gelmedi")
                t.finished.connect(t.deleteLater); t.start()

        conn.execute("UPDATE tur SET durum='TAMAMLANDI', bitis_tarihi=date('now','localtime') "
                     "WHERE id=?", (self._tur_id,))
        conn.commit(); conn.close()
        if sheets.aktif:
            t2 = _SheetsCallThread(sheets.tur_programi_guncelle, self._tur_adi, "TAMAMLANDI")
            t2.finished.connect(t2.deleteLater); t2.start()
        QMessageBox.information(self, "Tamam",
            f"✓ Tur kapatıldı. {len(eksik)} ürün stoktan düşüldü.")
        self._turleri_yukle()

    def _flash(self, m, r):
        self.lbl_flash.setText(m)
        self.lbl_flash.setStyleSheet(f"font-size:12px; font-weight:700; color:{r};")
        QTimer.singleShot(3500, lambda: self.lbl_flash.setText(""))

    def guncelle(self):
        self._turleri_yukle()


# ══════════════════════════════════════════════════════════════════════════
#  Yeni Tur Dialog
# ══════════════════════════════════════════════════════════════════════════
class YeniTurDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Yeni Tur Ekle"); self.setMinimumWidth(400)
        self.setStyleSheet(f"background:{RENK['yuzey']}; color:{RENK['metin']};")
        lay = QVBoxLayout(self); lay.setSpacing(12); lay.setContentsMargins(24,24,24,24)
        lbl = QLabel("Yeni Tur Ekle"); lbl.setStyleSheet("font-size:16px; font-weight:700;")
        lay.addWidget(lbl); lay.addWidget(AyiriciCizgi())

        def satir(et, w):
            row = QHBoxLayout(); l = QLabel(et); l.setFixedWidth(110)
            l.setStyleSheet(f"font-size:12px; font-weight:600; color:{RENK['metin2']};")
            row.addWidget(l); row.addWidget(w); lay.addLayout(row); return w

        self.tur_adi = satir("Tur Adı:", QLineEdit())
        self.tur_adi.setPlaceholderText("örn: 15 Temmuz Haftası"); self.tur_adi.setMinimumHeight(36)
        self.bas = satir("Başlangıç:", QDateEdit(QDate.currentDate()))
        self.bas.setCalendarPopup(True); self.bas.setDisplayFormat("dd.MM.yyyy")
        self.bit = satir("Bitiş:", QDateEdit(QDate.currentDate()))
        self.bit.setCalendarPopup(True); self.bit.setDisplayFormat("dd.MM.yyyy")
        lay.addWidget(QLabel("Notlar:"))
        self.notlar = QTextEdit(); self.notlar.setMaximumHeight(70)
        lay.addWidget(self.notlar)
        lay.addWidget(AyiriciCizgi())
        btn_lay = QHBoxLayout()
        bi = QPushButton("İptal"); bi.setObjectName("BtnIkincil"); bi.clicked.connect(self.reject)
        bk = QPushButton("Tur Oluştur"); bk.setObjectName("BtnAksan")
        bk.clicked.connect(lambda: self.accept() if self.tur_adi.text().strip() else
                           QMessageBox.warning(self,"Uyarı","Tur adı boş olamaz!"))
        btn_lay.addWidget(bi); btn_lay.addWidget(bk); lay.addLayout(btn_lay)

    def get_veri(self):
        return {"tur_adi": self.tur_adi.text().strip(),
                "baslangic_tarihi": self.bas.date().toString("yyyy-MM-dd"),
                "bitis_tarihi": self.bit.date().toString("yyyy-MM-dd"),
                "notlar": self.notlar.toPlainText().strip()}


# ══════════════════════════════════════════════════════════════════════════
#  3. TUR PROGRAMI
# ══════════════════════════════════════════════════════════════════════════
class TurProgramiSayfasi(QWidget):
    def __init__(self):
        super().__init__()
        self._build(); self.yukle()

    def _build(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(20,16,20,16); lay.setSpacing(12)
        ust = QHBoxLayout()
        lbl = QLabel("TUR PROGRAMI")
        lbl.setStyleSheet(f"font-size:10px; font-weight:700; letter-spacing:2px; color:{RENK['metin2']};")
        btn_yeni = QPushButton("+ Yeni Tur"); btn_yeni.setObjectName("BtnAksan")
        btn_yeni.clicked.connect(self._yeni)
        btn_sil = QPushButton("Sil"); btn_sil.setObjectName("BtnTehlike")
        btn_sil.clicked.connect(self._sil)
        ust.addWidget(lbl); ust.addStretch(); ust.addWidget(btn_sil); ust.addWidget(btn_yeni)
        lay.addLayout(ust)

        fil = QHBoxLayout()
        self.cb_durum = QComboBox(); self.cb_durum.setMinimumHeight(36)
        self.cb_durum.addItems(["Tüm Durumlar","BEKLIYOR","AKTIF","TAMAMLANDI"])
        self.cb_durum.currentIndexChanged.connect(self.yukle)
        fil.addWidget(QLabel("Durum:")); fil.addWidget(self.cb_durum); fil.addStretch()
        lay.addLayout(fil)

        self.tablo = QTableWidget(); self.tablo.setColumnCount(6)
        self.tablo.setHorizontalHeaderLabels(
            ["ID","TUR ADI","BAŞLANGIÇ","BİTİŞ","DURUM","YÜKLÜ ÜRÜN"])
        self.tablo.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tablo.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tablo.verticalHeader().setVisible(False); self.tablo.setAlternatingRowColors(True)
        self.tablo.doubleClicked.connect(self._durum_degistir)
        hh = self.tablo.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tablo.verticalHeader().setDefaultSectionSize(34)
        lay.addWidget(self.tablo, 1)
        aciklama = QLabel("Çift tıkla → durum değiştir (BEKLIYOR→AKTİF→TAMAMLANDI)")
        aciklama.setStyleSheet(f"font-size:11px; color:{RENK['metin3']};")
        lay.addWidget(aciklama)

    def yukle(self):
        d = self.cb_durum.currentText()
        conn = get_conn()
        rows = (conn.execute("SELECT * FROM tur ORDER BY baslangic_tarihi DESC").fetchall()
                if d == "Tüm Durumlar" else
                conn.execute("SELECT * FROM tur WHERE durum=? ORDER BY baslangic_tarihi DESC",
                             (d,)).fetchall())
        sayilar = {r["id"]: conn.execute(
            "SELECT COUNT(*) FROM tur_urun WHERE tur_id=?", (r["id"],)).fetchone()[0]
            for r in rows}
        conn.close()
        dr = {"BEKLIYOR": RENK["sari"], "AKTIF": RENK["yesil"], "TAMAMLANDI": RENK["metin3"]}
        self.tablo.setRowCount(len(rows))
        for i, r in enumerate(rows):
            vals = [str(r["id"]), r["tur_adi"], r["baslangic_tarihi"] or "-",
                    r["bitis_tarihi"] or "-", r["durum"], str(sayilar.get(r["id"],0))]
            for j, val in enumerate(vals):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                if j == 4:
                    item.setForeground(QColor(dr.get(r["durum"], RENK["metin"])))
                    item.setFont(QFont("", -1, QFont.Weight.Bold))
                self.tablo.setItem(i, j, item)

    def _yeni(self):
        dlg = YeniTurDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted: return
        d = dlg.get_veri()
        conn = get_conn()
        conn.execute("INSERT INTO tur (tur_adi,baslangic_tarihi,bitis_tarihi,durum,notlar) "
                     "VALUES (:tur_adi,:baslangic_tarihi,:bitis_tarihi,'BEKLIYOR',:notlar)", d)
        conn.commit(); conn.close()
        sheets = get_sheets()
        if sheets.aktif:
            t = _SheetsCallThread(
                sheets.tur_programi_ekle, d["tur_adi"], d["baslangic_tarihi"],
                d["bitis_tarihi"], "BEKLIYOR", d["notlar"])
            t.finished.connect(t.deleteLater); t.start()
        self.yukle()

    def _sil(self):
        rows = self.tablo.selectionModel().selectedRows()
        if not rows: return
        tid  = int(self.tablo.item(rows[0].row(), 0).text())
        tadi = self.tablo.item(rows[0].row(), 1).text()
        if QMessageBox.question(self, "Sil", f"'{tadi}' turu silinecek. Emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            ) != QMessageBox.StandardButton.Yes: return
        conn = get_conn()
        conn.execute("DELETE FROM tur_urun WHERE tur_id=?", (tid,))
        conn.execute("DELETE FROM tur WHERE id=?", (tid,))
        conn.commit(); conn.close(); self.yukle()

    def _durum_degistir(self):
        rows = self.tablo.selectionModel().selectedRows()
        if not rows: return
        tid  = int(self.tablo.item(rows[0].row(), 0).text())
        tadi = self.tablo.item(rows[0].row(), 1).text()
        simdi= self.tablo.item(rows[0].row(), 4).text()
        sira = ["BEKLIYOR","AKTIF","TAMAMLANDI"]
        if simdi not in sira: simdi="BEKLIYOR"
        yeni = sira[(sira.index(simdi) + 1) % len(sira)]
        conn = get_conn(); conn.execute("UPDATE tur SET durum=? WHERE id=?", (yeni, tid))
        conn.commit(); conn.close()
        sheets = get_sheets()
        if sheets.aktif: sheets.tur_programi_guncelle(tadi, yeni)
        self.yukle()

    def guncelle(self): self.yukle()


# ══════════════════════════════════════════════════════════════════════════
#  ANA TUR SAYFASI
# ══════════════════════════════════════════════════════════════════════════
class TurSayfasi(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(0)

        self.sheets_band = QFrame(); self.sheets_band.setFixedHeight(30)
        bl = QHBoxLayout(self.sheets_band); bl.setContentsMargins(20,0,20,0)
        self.lbl_sheets = QLabel("")
        self.lbl_sheets.setStyleSheet("font-size:11px; font-weight:600;")
        bl.addWidget(self.lbl_sheets); bl.addStretch()
        lay.addWidget(self.sheets_band)
        lay.addWidget(AyiriciCizgi())

        self.tabs = QTabWidget(); self.tabs.setDocumentMode(True)
        self.cikis_s   = TuraCikisSayfasi()
        self.donus_s   = TurDonusSayfasi()
        self.program_s = TurProgramiSayfasi()
        self.tabs.addTab(self.cikis_s,   "  ↑  Tura Çıkış  ")
        self.tabs.addTab(self.donus_s,   "  ↓  Turdan Dönüş  ")
        self.tabs.addTab(self.program_s, "  📋  Tur Programı  ")
        self.tabs.currentChanged.connect(self._sekme)
        lay.addWidget(self.tabs, 1)
        self._sheets_goster()

    def _sheets_goster(self):
        s = get_sheets()
        if s.aktif and not s.hata_msg:
            self.sheets_band.setStyleSheet(f"background:{RENK['yesil_bg']};")
            self.lbl_sheets.setText("● Sheets bağlı — anlık senkronize")
            self.lbl_sheets.setStyleSheet(f"font-size:11px; font-weight:600; color:{RENK['yesil']};")
        else:
            self.sheets_band.setStyleSheet(f"background:{RENK['yuzey2']};")
            self.lbl_sheets.setText(f"○ Sheets: {s.hata_msg or 'bağlı değil'}")
            self.lbl_sheets.setStyleSheet(f"font-size:11px; font-weight:600; color:{RENK['metin3']};")

    def _sekme(self, idx):
        if idx == 0: self.cikis_s.guncelle()
        elif idx == 1: self.donus_s.guncelle()
        elif idx == 2: self.program_s.guncelle()
        self._sheets_goster()
