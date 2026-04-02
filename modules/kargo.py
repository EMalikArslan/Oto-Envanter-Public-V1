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
    """Yatay A6 @ 200dpi — buyuk font, Turkce uyumlu, barkod yok."""
    os.makedirs(LABELS_DIR, exist_ok=True)
    W, H = 1165, 827
    img  = Image.new("RGB",(W,H),"white")
    draw = ImageDraw.Draw(img)
    fp_k = _sec_font(True)
    fp_n = _sec_font(False)

    def f(yol, pt):
        if yol:
            try: return ImageFont.truetype(yol, pt)
            except: pass
        return ImageFont.load_default()

    f_firma  = f(fp_k, 62)
    f_buyuk  = f(fp_k, 54)
    f_orta_k = f(fp_k, 40)
    f_orta_n = f(fp_n, 40)
    f_kucuk_n= f(fp_n, 28)
    f_etiket = f(fp_k, 22)
    f_mini   = f(fp_n, 20)

    PAD  = 44
    ORTA = W // 2
    SH   = 96  # header height

    # Cerceve
    draw.rectangle([(6,6),(W-6,H-6)], outline="black", width=3)
    draw.rectangle([(6,6),(W-6,SH)],  fill="#1A1917")

    # Logo
    if os.path.exists(LOGO_PATH):
        try:
            logo = Image.open(LOGO_PATH).convert("RGBA")
            lh   = SH - 18
            lw   = int(logo.size[0] * lh / logo.size[1])
            logo = logo.resize((lw, lh), Image.Resampling.LANCZOS)
            wh   = Image.new("RGB", (lw, lh), "white")
            wh.paste(logo.convert("RGB"), mask=logo.split()[3])
            img.paste(wh, (PAD, 9))
        except:
            pass

    draw.text((W//2, SH//2+4), "ARES OTO ELEKTRONIK",
              fill="white", font=f_firma, anchor="mm")
    draw.line([(ORTA, SH+8),(ORTA, H-6)], fill="#BBBBBB", width=2)

    # SOL — GONDERICI
    y = SH + PAD
    draw.text((PAD, y), "GONDERICI", fill="#888888", font=f_etiket)
    y += 28
    draw.text((PAD, y), _tr_k(GONDERICI["isim"]), fill="black", font=f_orta_k)
    y += 50
    draw.text((PAD, y), f"Anlasma: {GONDERICI['anlasma_kodu']}",
              fill="#555555", font=f_kucuk_n)
    if icerik and icerik != "-":
        y += 42
        draw.text((PAD, y), "ICERIK", fill="#888888", font=f_etiket)
        y += 26
        draw.text((PAD, y), _tr_k(str(icerik))[:36], fill="black", font=f_kucuk_n)
    draw.text((PAD, H-PAD-34), f"Kargo No: K{kargo_id:06d}",
              fill="#AAAAAA", font=f_kucuk_n)
    draw.text((PAD, H-PAD+2), datetime.now().strftime("%d.%m.%Y"),
              fill="#AAAAAA", font=f_mini)

    # SAG — ALICI
    sx = ORTA + PAD
    y  = SH + PAD
    draw.text((sx, y), "ALICI", fill="#888888", font=f_etiket)
    y += 28
    draw.text((sx, y), _tr_k(alici_adi)[:18], fill="black", font=f_buyuk)
    y += 68

    adres   = _tr_k(alici_adres)
    satirlar= []
    satir   = []
    for kelime in adres.split():
        test = " ".join(satir + [kelime])
        if len(test) <= 26:
            satir.append(kelime)
        else:
            if satir: satirlar.append(" ".join(satir))
            satir = [kelime]
    if satir: satirlar.append(" ".join(satir))

    for s in satirlar[:4]:
        draw.text((sx, y), s, fill="black", font=f_orta_n)
        y += 48

    if alici_telefon and alici_telefon != "-":
        y += 8
        draw.text((sx, y), f"Tel: {_tr_k(alici_telefon)}",
                  fill="#333333", font=f_orta_k)

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
