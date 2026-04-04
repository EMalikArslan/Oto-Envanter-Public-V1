import os, sys
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QFrame, QMessageBox, QDialog,
    QTabWidget, QProgressDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from core.database import get_conn
from core.tema import RENK

def _base():
    return os.path.dirname(sys.executable) if getattr(sys,"frozen",False) else \
           os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BASE       = _base()
LABELS_DIR = os.path.join(BASE, "labels")
ASSETS_DIR = os.path.join(BASE, "assets")
LOGO_PATH  = os.path.join(ASSETS_DIR, "logo.png")

TR_K = str.maketrans("ğĞışİöÖüÜçÇ","gGisiOoUuCc")
def _tr_k(s): return str(s or "").translate(TR_K)

GONDERICI = {
    "isim":        "Burc BabuCoglu",
    "anlasma_kodu":"603546342",
    "adres":       "Istanbul",
    "telefon":     "",
}

def _sec_font(kalin=True):
    k=["C:/Windows/Fonts/arialbd.ttf","C:/Windows/Fonts/calibrib.ttf",
       "C:/Windows/Fonts/verdanab.ttf",
       "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
       "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
    n=["C:/Windows/Fonts/arial.ttf","C:/Windows/Fonts/calibri.ttf",
       "C:/Windows/Fonts/verdana.ttf",
       "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
       "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    for p in (k if kalin else n):
        if os.path.exists(p): return p
    return None


def kargo_etiketi_olustur(kargo_id, alici_adi, alici_adres, alici_telefon, icerik=""):
    """40x30mm @ 300dpi yatay — kargo etiketi, Turkce uyumlu."""
    os.makedirs(LABELS_DIR, exist_ok=True)
    W, H = 472, 354   # 40x30 mm @ 300 dpi
    PAD  = 10
    img  = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)
    fp_k = _sec_font(True)
    fp_n = _sec_font(False)

    def f(yol, pt):
        if yol:
            try: return ImageFont.truetype(yol, pt)
            except: pass
        return ImageFont.load_default()

    f_firma      = f(fp_k, 22)
    f_baslik     = f(fp_k, 20)
    f_alici      = f(fp_k, 28)
    f_gon_isim   = f(fp_k, 18)   # Gönderici isim — kalın + büyük
    f_gon_detay  = f(fp_n, 16)   # Gönderici detay
    f_kucuk      = f(fp_n, 15)
    f_mini       = f(fp_n, 13)

    SH   = 42   # header yüksekliği
    ORTA = W // 2

    # ── Çerçeve ───────────────────────────────────────────────────────────
    draw.rectangle([(2, 2), (W-2, H-2)], outline="black", width=2)

    # ── Header (koyu arka plan) ───────────────────────────────────────────
    draw.rectangle([(2, 2), (W-2, SH)], fill="#1A1917")

    if os.path.exists(LOGO_PATH):
        try:
            logo = Image.open(LOGO_PATH).convert("RGBA")
            lh   = SH - 10
            lw   = int(logo.size[0] * lh / logo.size[1])
            logo = logo.resize((lw, lh), Image.Resampling.LANCZOS)
            bg   = Image.new("RGB", (lw, lh), "#1A1917")
            bg.paste(logo.convert("RGB"), mask=logo.split()[3])
            img.paste(bg, (PAD, 5))
        except:
            pass

    draw.text((W//2, SH//2 + 2), "ARES OTO ELEKTRONIK",
              fill="white", font=f_firma, anchor="mm")

    # ── Orta dikey ayırıcı ────────────────────────────────────────────────
    draw.line([(ORTA, SH+4), (ORTA, H-4)], fill="#BBBBBB", width=1)

    # ── SOL — GÖNDERİCİ ──────────────────────────────────────────────────
    y = SH + 8
    draw.text((PAD, y), "GONDERICI", fill="#888888", font=f_kucuk); y += 20
    draw.text((PAD, y), _tr_k(GONDERICI["isim"]), fill="black", font=f_gon_isim); y += 24
    draw.text((PAD, y), f"Anl: {GONDERICI['anlasma_kodu']}", fill="#555555", font=f_gon_detay); y += 20

    if icerik and icerik != "-":
        draw.text((PAD, y), "ICERIK:", fill="#888888", font=f_kucuk); y += 18
        draw.text((PAD, y), _tr_k(str(icerik))[:22], fill="black", font=f_gon_detay)

    # Kargo no + tarih (sol alt)
    draw.text((PAD, H-PAD-24), f"K{kargo_id:06d}", fill="#555555", font=f_kucuk)
    draw.text((PAD, H-PAD- 8), datetime.now().strftime("%d.%m.%Y"), fill="#AAAAAA", font=f_mini)

    # ── SAĞ — ALICI ───────────────────────────────────────────────────────
    sx = ORTA + 8
    y  = SH + 8
    draw.text((sx, y), "ALICI", fill="#888888", font=f_mini); y += 16
    draw.text((sx, y), _tr_k(alici_adi)[:14], fill="black", font=f_alici); y += 34

    # Adres kelime sarma
    adres    = _tr_k(alici_adres)
    satirlar = []
    satir    = []
    for kelime in adres.split():
        test = " ".join(satir + [kelime])
        if len(test) <= 20:
            satir.append(kelime)
        else:
            if satir: satirlar.append(" ".join(satir))
            satir = [kelime]
    if satir: satirlar.append(" ".join(satir))

    for s in satirlar[:3]:
        draw.text((sx, y), s, fill="black", font=f_kucuk); y += 19

    if alici_telefon and alici_telefon != "-":
        y += 4
        draw.text((sx, y), f"Tel: {_tr_k(alici_telefon)}", fill="#333333", font=f_kucuk)

    path = os.path.join(LABELS_DIR, f"kargo_{kargo_id}.png")
    img.save(path)
    return path



# ── Arka plan thread'i (donma önlemi) ────────────────────────────────────────
class KargoThread(QThread):
    bitti = pyqtSignal(str, str)   # (kargo_no, dosya_yolu)
    hata  = pyqtSignal(str)

    def __init__(self, kargo_id, alici_adi, alici_adres, alici_telefon, icerik):
        super().__init__()
        self.kargo_id      = kargo_id
        self.alici_adi     = alici_adi
        self.alici_adres   = alici_adres
        self.alici_telefon = alici_telefon
        self.icerik        = icerik

    def run(self):
        try:
            yol = kargo_etiketi_olustur(
                self.kargo_id, self.alici_adi,
                self.alici_adres, self.alici_telefon, self.icerik
            )
            self.bitti.emit(f"K{self.kargo_id:06d}", yol)
        except Exception as e:
            self.hata.emit(str(e))


# ── Yeni Kargo Formu ──────────────────────────────────────────────────────────
class YeniKargoSayfasi(QWidget):

    def __init__(self):
        super().__init__()
        self._thread = None
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)

        baslik = QLabel("Kargo Etiketi Oluştur")
        baslik.setStyleSheet("font-size:16px;font-weight:bold;color:#fff;")
        lay.addWidget(baslik)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Kayıtlı müşteri seçimi
        self.musteri_cb = QComboBox()
        self.musteri_cb.setMinimumHeight(34)
        self.musteri_cb.addItem("— Manuel Giriş —", None)
        self.musteri_cb.currentIndexChanged.connect(self._musteri_sec)
        form.addRow("Kayıtlı Müşteri", self.musteri_cb)

        self.alici_adi     = QLineEdit(); self.alici_adi.setPlaceholderText("Alıcı adı soyadı")
        self.alici_adres   = QLineEdit(); self.alici_adres.setPlaceholderText("Adres")
        self.alici_telefon = QLineEdit(); self.alici_telefon.setPlaceholderText("05XX XXX XXXX")
        self.icerik        = QLineEdit(); self.icerik.setPlaceholderText("Ürün / içerik açıklaması")

        form.addRow("Alıcı Adı *",  self.alici_adi)
        form.addRow("Adres",        self.alici_adres)
        form.addRow("Telefon",      self.alici_telefon)
        form.addRow("İçerik",       self.icerik)
        lay.addLayout(form)

        self._musteri_yukle()

        self.btn = QPushButton("📦  Etiket Oluştur")
        self.btn.setFixedHeight(40)
        self.btn.setStyleSheet(
            "background:#C0392B;color:#fff;font-weight:bold;"
            "border-radius:6px;font-size:14px;"
        )
        self.btn.clicked.connect(self._olustur)
        lay.addWidget(self.btn)

        self.durum_lbl = QLabel("")
        self.durum_lbl.setStyleSheet("color:#aaa;font-size:12px;")
        lay.addWidget(self.durum_lbl)
        lay.addStretch()

    def guncelle(self):
        self._musteri_yukle()

    def _musteri_yukle(self):
        """DB'den müşterileri çekip combo'ya doldur."""
        try:
            with get_conn() as conn:
                rows = conn.execute(
                    "SELECT id, ad_soyad, telefon, adres FROM musteri ORDER BY ad_soyad"
                ).fetchall()
        except Exception:
            rows = []
        self.musteri_cb.blockSignals(True)
        # Mevcut seçimi koru
        secili = self.musteri_cb.currentData()
        self.musteri_cb.clear()
        self.musteri_cb.addItem("— Manuel Giriş —", None)
        for r in rows:
            self.musteri_cb.addItem(f"{r[1]}  ({r[2] or '—'})", r[0])
        # Kaydedilen seçimi geri yükle
        if secili:
            for i in range(self.musteri_cb.count()):
                if self.musteri_cb.itemData(i) == secili:
                    self.musteri_cb.setCurrentIndex(i); break
        self.musteri_cb.blockSignals(False)

    def _musteri_sec(self, idx):
        mid = self.musteri_cb.currentData()
        if not mid:
            return
        try:
            with get_conn() as conn:
                row = conn.execute(
                    "SELECT ad_soyad, adres, telefon FROM musteri WHERE id=?", (mid,)
                ).fetchone()
            if row:
                self.alici_adi.setText(row[0] or "")
                self.alici_adres.setText(row[1] or "")
                self.alici_telefon.setText(row[2] or "")
        except Exception:
            pass

    def _olustur(self):
        adi = self.alici_adi.text().strip()
        if not adi:
            QMessageBox.warning(self, "Eksik", "Alıcı adı zorunludur.")
            return

        # Veritabanına kaydet
        try:
            with get_conn() as conn:
                cur = conn.execute(
                    "INSERT INTO kargo (alici_adi, alici_adres, alici_telefon, icerik, durum) "
                    "VALUES (?,?,?,?,'hazirlaniyor')",
                    (adi,
                     self.alici_adres.text().strip(),
                     self.alici_telefon.text().strip(),
                     self.icerik.text().strip())
                )
                kid = cur.lastrowid
        except Exception as e:
            QMessageBox.critical(self, "DB Hatası", str(e))
            return

        self.btn.setEnabled(False)
        self.durum_lbl.setText("Etiket oluşturuluyor...")

        self._thread = KargoThread(
            kid, adi,
            self.alici_adres.text().strip(),
            self.alici_telefon.text().strip(),
            self.icerik.text().strip()
        )
        self._thread.bitti.connect(self._bitti)
        self._thread.hata.connect(self._hata)
        self._thread.start()

    def _bitti(self, kargo_no, yol):
        self.btn.setEnabled(True)
        self.durum_lbl.setText(f"✓ {kargo_no} oluşturuldu")
        QMessageBox.information(
            self, "Etiket Hazır",
            f"Kargo No: {kargo_no}\n\nDosya: {yol}\n\nEtiket klasöründe bulabilirsiniz."
        )
        # Formu temizle
        for w in [self.alici_adi, self.alici_adres, self.alici_telefon, self.icerik]:
            w.clear()

    def _hata(self, mesaj):
        self.btn.setEnabled(True)
        self.durum_lbl.setText("Hata oluştu")
        QMessageBox.critical(self, "Hata", f"Etiket oluşturulamadı:\n{mesaj}")


# ── Kargo Geçmişi Tablosu ─────────────────────────────────────────────────────
class KargoGecmisiSayfasi(QWidget):

    SUTUNLAR = ["No", "Alıcı", "Adres", "Telefon", "İçerik", "Durum", "Tarih"]

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)

        self.tablo = QTableWidget()
        self.tablo.setColumnCount(len(self.SUTUNLAR))
        self.tablo.setHorizontalHeaderLabels(self.SUTUNLAR)
        self.tablo.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tablo.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tablo.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tablo.verticalHeader().setVisible(False)
        self.tablo.setAlternatingRowColors(True)
        lay.addWidget(self.tablo)

        self.guncelle()

    def guncelle(self):
        try:
            with get_conn() as conn:
                rows = conn.execute(
                    "SELECT id, alici_adi, alici_adres, alici_telefon, icerik, durum, "
                    "olusturma FROM kargo ORDER BY id DESC LIMIT 200"
                ).fetchall()
        except Exception:
            rows = []

        self.tablo.setRowCount(len(rows))
        for r, row in enumerate(rows):
            vals = [
                f"K{row[0]:06d}", row[1] or "", row[2] or "",
                row[3] or "", row[4] or "", row[5] or "",
                (row[6] or "")[:16]
            ]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(str(v))
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.tablo.setItem(r, c, it)


# ── Ana Sekme Widget ───────────────────────────────────────────────────────────
class KargoSayfasi(QWidget):

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        self.yeni_s   = YeniKargoSayfasi()
        self.gecmis_s = KargoGecmisiSayfasi()

        self.tabs.addTab(self.yeni_s,   "  📦  Yeni Kargo  ")
        self.tabs.addTab(self.gecmis_s, "  📋  Kargo Geçmişi  ")
        self.tabs.currentChanged.connect(self._sekme)
        lay.addWidget(self.tabs, 1)

    def _sekme(self, idx):
        if idx == 1:
            self.gecmis_s.guncelle()

    def guncelle(self):
        self._sekme(self.tabs.currentIndex())
