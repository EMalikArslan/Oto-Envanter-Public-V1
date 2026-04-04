import os, sys
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QFrame, QMessageBox, QDialog
)
from PyQt6.QtCore import Qt

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

    f_firma  = f(fp_k, 22)
    f_baslik = f(fp_k, 20)
    f_alici  = f(fp_k, 28)
    f_orta   = f(fp_n, 18)
    f_kucuk  = f(fp_n, 15)
    f_mini   = f(fp_n, 13)

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
    draw.text((PAD, y), "GONDERICI", fill="#888888", font=f_mini); y += 16
    draw.text((PAD, y), _tr_k(GONDERICI["isim"]), fill="black", font=f_kucuk); y += 19
    draw.text((PAD, y), f"Anl: {GONDERICI['anlasma_kodu']}", fill="#555555", font=f_mini); y += 16

    if icerik and icerik != "-":
        draw.text((PAD, y), "ICERIK:", fill="#888888", font=f_mini); y += 14
        draw.text((PAD, y), _tr_k(str(icerik))[:22], fill="black", font=f_mini)

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
        if idx == 0: self.yeni_s.guncelle()
        elif idx == 1: self.gecmis_s.guncelle()

    def guncelle(self):
        self._sekme(self.tabs.currentIndex())
