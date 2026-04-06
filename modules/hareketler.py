"""
modules/hareketler.py
─────────────────────
Stok Hareketleri — 3 sekme:

  1. Hızlı Satış   — barkod okuyucu veya listeden seç, stoktan düş
  2. Mal Girişi    — barkod veya toplu CSV ile stok artır
  3. Hareket Geçmişi — tüm satış ve girişlerin filtrelenebilir logu
"""

import os
import sqlite3
import pandas as pd
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QSplitter,
    QPushButton, QLabel, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFrame, QComboBox, QTextEdit,
    QMessageBox, QDialog, QDoubleSpinBox, QSpinBox, QFileDialog,
    QScrollArea, QSizePolicy, QDateEdit
)
from PyQt6.QtCore import Qt, QTimer, QDate, QThread, pyqtSignal as _Signal
from PyQt6.QtGui import QColor, QFont

from core.database import get_conn, v, to_int
from core.tema import RENK
from core.widgets import StatKart, AyiriciCizgi, Badge
from core.sheets import get_sheets


# ── Sheets arka plan thread'i (UI donmasını önler) ────────────────────────────
class _SheetsCallThread(QThread):
    """Herhangi bir sheets callable'ını arka planda çalıştırır."""
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn = fn; self._args = args; self._kwargs = kwargs
    def run(self):
        try: self._fn(*self._args, **self._kwargs)
        except Exception: pass

# Hareket tipi renkleri
TIP_RENK = {
    "SATIS":     RENK["aksan"],
    "MAL_GIRIS": RENK["yesil"],
    "DUZELTME":  RENK["mavi"],
}
TIP_ETIKET = {
    "SATIS":     "SATIŞ",
    "MAL_GIRIS": "MAL GİRİŞİ",
    "DUZELTME":  "DÜZELTME",
}


# ── Yardımcılar ───────────────────────────────────────────────────────────
def _stok_bul(stok_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM stok WHERE id=?", (stok_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def _stok_guncelle(stok_id: int, delta: int):
    """Stok miktarını delta kadar değiştir, yeni miktarı döner."""
    conn = get_conn()
    conn.execute(
        "UPDATE stok SET stok_miktari = MAX(0, stok_miktari + ?), "
        "guncelleme = datetime('now','localtime') WHERE id=?",
        (delta, stok_id))
    conn.commit()
    yeni = conn.execute(
        "SELECT stok_miktari FROM stok WHERE id=?", (stok_id,)).fetchone()[0]
    conn.close()
    return yeni

def _hareket_kaydet(tip, stok_id, adet, birim_fiyat=0, toplam=0,
                    musteri="", tedarikci="", giris_fiyati=0,
                    notlar="", stok_sonrasi=0):
    conn = get_conn()
    conn.execute("""INSERT INTO hareket
        (hareket_tipi, stok_id, adet, birim_fiyat, toplam_tutar,
         musteri_adi, tedarikci, giris_fiyati, notlar, stok_sonrasi)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (tip, stok_id, adet, birim_fiyat, toplam,
         musteri, tedarikci, giris_fiyati, notlar, stok_sonrasi))
    conn.commit()
    conn.close()


# ══════════════════════════════════════════════════════════════════════════
#  BARKOD INPUT (tekrar kullanım)
# ══════════════════════════════════════════════════════════════════════════
from PyQt6.QtCore import pyqtSignal

class BarkodInput(QLineEdit):
    barkod_okundu = pyqtSignal(str)
    def __init__(self, placeholder="Barkod okutun veya ID girin..."):
        super().__init__()
        self.setPlaceholderText(placeholder)
        self.setMinimumHeight(48)
        self.setStyleSheet(f"""
            QLineEdit {{
                font-size: 18px; font-weight: 700;
                border: 2px solid {RENK['cizgi_koyu']};
                border-radius: 8px; padding: 8px 14px;
                background: {RENK['yuzey']}; color: {RENK['metin']};
            }}
            QLineEdit:focus {{ border-color: {RENK['metin']}; }}
        """)
        self.returnPressed.connect(self._emit)
    def _emit(self):
        val = self.text().strip()
        if val:
            self.barkod_okundu.emit(val)
            self.clear()


# ══════════════════════════════════════════════════════════════════════════
#  SEPET SATIRI KARTI
# ══════════════════════════════════════════════════════════════════════════
class SepetSatiri(QFrame):
    """Satış sepetindeki tek ürün satırı — adet, fiyat, sil."""
    silindi   = pyqtSignal(int)       # stok_id
    degisti   = pyqtSignal()

    def __init__(self, stok_id, kategori, marka, yaygin_ad, ref1,
                 varsayilan_fiyat=0.0):
        super().__init__()
        self.stok_id = stok_id
        self.setObjectName("KartKoyu")
        self.setStyleSheet(
            f"QFrame#KartKoyu {{ background: {RENK['yuzey2']}; "
            f"border-radius: 8px; border: 1px solid {RENK['cizgi']}; }}")
        self.setFixedHeight(64)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 6, 12, 6)
        lay.setSpacing(10)

        # Ürün bilgisi
        bilgi = QVBoxLayout()
        bilgi.setSpacing(1)
        lbl_urun = QLabel(f"{marka}  /  {yaygin_ad}")
        lbl_urun.setStyleSheet(f"font-weight: 700; font-size: 13px; color: {RENK['metin']};")
        lbl_ref  = QLabel(f"ID:{stok_id}  {kategori}  {ref1 if ref1 != '-' else ''}")
        lbl_ref.setStyleSheet(f"font-size: 11px; color: {RENK['metin2']};")
        bilgi.addWidget(lbl_urun)
        bilgi.addWidget(lbl_ref)
        lay.addLayout(bilgi, 3)

        # Adet
        lbl_a = QLabel("Adet:")
        lbl_a.setStyleSheet(f"font-size: 12px; color: {RENK['metin2']};")
        lay.addWidget(lbl_a)
        self.sb_adet = QSpinBox()
        self.sb_adet.setRange(1, 9999)
        self.sb_adet.setValue(1)
        self.sb_adet.setFixedWidth(70)
        self.sb_adet.setMinimumHeight(32)
        self.sb_adet.valueChanged.connect(self.degisti.emit)
        lay.addWidget(self.sb_adet)

        # Fiyat
        lbl_f = QLabel("₺")
        lbl_f.setStyleSheet(f"font-size: 12px; color: {RENK['metin2']};")
        lay.addWidget(lbl_f)
        self.sb_fiyat = QDoubleSpinBox()
        self.sb_fiyat.setRange(0, 9_999_999)
        self.sb_fiyat.setDecimals(2)
        self.sb_fiyat.setValue(float(varsayilan_fiyat) if varsayilan_fiyat else 0.0)
        self.sb_fiyat.setFixedWidth(110)
        self.sb_fiyat.setMinimumHeight(32)
        self.sb_fiyat.valueChanged.connect(self.degisti.emit)
        lay.addWidget(self.sb_fiyat)

        # Tutar
        self.lbl_tutar = QLabel("₺0,00")
        self.lbl_tutar.setFixedWidth(90)
        self.lbl_tutar.setStyleSheet(
            f"font-weight: 700; font-size: 13px; color: {RENK['metin']}; "
            f"text-align: right;")
        self.lbl_tutar.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self.lbl_tutar)

        # Sil
        btn_sil = QPushButton("✕")
        btn_sil.setFixedSize(30, 30)
        btn_sil.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {RENK['metin3']}; "
            f"border: none; font-size: 14px; }}"
            f"QPushButton:hover {{ color: {RENK['aksan']}; }}")
        btn_sil.clicked.connect(lambda: self.silindi.emit(self.stok_id))
        lay.addWidget(btn_sil)

        self.degisti.connect(self._guncelle_tutar)
        self._guncelle_tutar()

    def _guncelle_tutar(self):
        t = self.sb_adet.value() * self.sb_fiyat.value()
        self.lbl_tutar.setText(f"₺{t:,.2f}")

    def get_veri(self):
        adet  = self.sb_adet.value()
        fiyat = self.sb_fiyat.value()
        return adet, fiyat, adet * fiyat


# ══════════════════════════════════════════════════════════════════════════
#  1. HIZLI SATIŞ
# ══════════════════════════════════════════════════════════════════════════
class HizliSatisSayfasi(QWidget):

    def __init__(self):
        super().__init__()
        self._sepet = {}   # stok_id → (SepetSatiri, stok_bilgisi)
        self._build()

    def _build(self):
        ana = QHBoxLayout(self)
        ana.setContentsMargins(20, 16, 20, 16)
        ana.setSpacing(16)

        # ── SOL: Ürün arama / barkod ────────────────────────────────────
        sol = QVBoxLayout()
        sol.setSpacing(12)

        lbl_giris = QLabel("ÜRÜN EKLE")
        lbl_giris.setStyleSheet(
            f"font-size: 10px; font-weight: 700; letter-spacing: 2px; color: {RENK['metin2']};")
        sol.addWidget(lbl_giris)

        # Barkod
        barkod_kart = QFrame()
        barkod_kart.setObjectName("Kart")
        barkod_kart.setStyleSheet(
            f"QFrame#Kart {{ background: {RENK['yuzey']}; border-radius: 10px; "
            f"border: 1px solid {RENK['cizgi']}; }}")
        bk_lay = QVBoxLayout(barkod_kart)
        bk_lay.setContentsMargins(14, 12, 14, 12)
        bk_lay.setSpacing(8)
        lbl_bk = QLabel("BARKOD / ID")
        lbl_bk.setStyleSheet(
            f"font-size: 10px; font-weight: 700; letter-spacing: 1.5px; color: {RENK['metin2']};")
        bk_lay.addWidget(lbl_bk)
        self.barkod_in = BarkodInput()
        self.barkod_in.barkod_okundu.connect(self._barkod_isle)
        bk_lay.addWidget(self.barkod_in)
        self.lbl_flash = QLabel("")
        self.lbl_flash.setStyleSheet("font-size: 12px; font-weight: 700;")
        bk_lay.addWidget(self.lbl_flash)
        sol.addWidget(barkod_kart)

        # Liste ile arama
        ara_kart = QFrame()
        ara_kart.setObjectName("Kart")
        ara_kart.setStyleSheet(
            f"QFrame#Kart {{ background: {RENK['yuzey']}; border-radius: 10px; "
            f"border: 1px solid {RENK['cizgi']}; }}")
        ak_lay = QVBoxLayout(ara_kart)
        ak_lay.setContentsMargins(14, 12, 14, 12)
        ak_lay.setSpacing(8)

        lbl_ara = QLabel("VEYA LİSTEDEN SEÇ")
        lbl_ara.setStyleSheet(
            f"font-size: 10px; font-weight: 700; letter-spacing: 1.5px; color: {RENK['metin2']};")
        ak_lay.addWidget(lbl_ara)

        fil_lay = QHBoxLayout()
        self.ara_txt = QLineEdit()
        self.ara_txt.setPlaceholderText("Marka, model, referans ara...")
        self.ara_txt.setMinimumHeight(36)
        self.ara_txt.textChanged.connect(self._liste_filtrele)
        self.cb_kat = QComboBox()
        self.cb_kat.setMinimumHeight(36)
        self.cb_kat.addItems(["Tüm Kategoriler", "Beyin", "ABS", "Plastik"])
        self.cb_kat.currentIndexChanged.connect(self._liste_filtrele)
        fil_lay.addWidget(self.ara_txt, 2)
        fil_lay.addWidget(self.cb_kat, 1)
        ak_lay.addLayout(fil_lay)

        self.liste_tablo = QTableWidget()
        self.liste_tablo.setColumnCount(5)
        self.liste_tablo.setHorizontalHeaderLabels(
            ["ID", "KATEGORİ", "MARKA", "YAYGIN AD", "STOK"])
        self.liste_tablo.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.liste_tablo.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.liste_tablo.verticalHeader().setVisible(False)
        self.liste_tablo.setAlternatingRowColors(True)
        hh = self.liste_tablo.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.liste_tablo.verticalHeader().setDefaultSectionSize(30)
        self.liste_tablo.setMaximumHeight(260)
        self.liste_tablo.doubleClicked.connect(self._listeden_ekle)
        ak_lay.addWidget(self.liste_tablo)

        btn_ekle_liste = QPushButton("+ Seçili Ürünü Sepete Ekle")
        btn_ekle_liste.setObjectName("BtnIkincil")
        btn_ekle_liste.clicked.connect(self._listeden_ekle)
        ak_lay.addWidget(btn_ekle_liste)
        sol.addWidget(ara_kart, 1)

        ana.addLayout(sol, 5)

        # ── SAĞ: Sepet ──────────────────────────────────────────────────
        sag = QVBoxLayout()
        sag.setSpacing(12)

        lbl_sepet = QLabel("SATIŞ SEPETİ")
        lbl_sepet.setStyleSheet(
            f"font-size: 10px; font-weight: 700; letter-spacing: 2px; color: {RENK['metin2']};")
        sag.addWidget(lbl_sepet)

        # Kaydırılabilir sepet alanı
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"QScrollArea {{ border: 1px solid {RENK['cizgi']}; border-radius: 10px; "
            f"background: {RENK['yuzey']}; }}")
        self.sepet_container = QWidget()
        self.sepet_lay = QVBoxLayout(self.sepet_container)
        self.sepet_lay.setContentsMargins(8, 8, 8, 8)
        self.sepet_lay.setSpacing(6)
        self.sepet_lay.addStretch()
        scroll.setWidget(self.sepet_container)
        sag.addWidget(scroll, 1)

        # Müşteri + not
        ek_lay = QHBoxLayout()
        self.txt_musteri = QLineEdit()
        self.txt_musteri.setPlaceholderText("Müşteri adı (opsiyonel)")
        self.txt_musteri.setMinimumHeight(36)
        ek_lay.addWidget(self.txt_musteri, 2)
        self.txt_not = QLineEdit()
        self.txt_not.setPlaceholderText("Not")
        self.txt_not.setMinimumHeight(36)
        ek_lay.addWidget(self.txt_not, 2)
        sag.addLayout(ek_lay)

        # Toplam + tamamla
        alt_kart = QFrame()
        alt_kart.setObjectName("Kart")
        alt_kart.setStyleSheet(
            f"QFrame#Kart {{ background: {RENK['yuzey']}; border-radius: 10px; "
            f"border: 1px solid {RENK['cizgi']}; }}")
        alt_lay2 = QVBoxLayout(alt_kart)
        alt_lay2.setContentsMargins(16, 12, 16, 12)
        alt_lay2.setSpacing(10)

        toplam_lay = QHBoxLayout()
        lbl_tot_bas = QLabel("TOPLAM TUTAR")
        lbl_tot_bas.setStyleSheet(
            f"font-size: 11px; font-weight: 700; letter-spacing: 1px; color: {RENK['metin2']};")
        self.lbl_toplam = QLabel("₺0,00")
        self.lbl_toplam.setStyleSheet(
            f"font-size: 26px; font-weight: 700; color: {RENK['metin']};")
        self.lbl_toplam.setAlignment(Qt.AlignmentFlag.AlignRight)
        toplam_lay.addWidget(lbl_tot_bas)
        toplam_lay.addStretch()
        toplam_lay.addWidget(self.lbl_toplam)
        alt_lay2.addLayout(toplam_lay)

        btn_tamamla = QPushButton("✓  Satışı Tamamla")
        btn_tamamla.setObjectName("BtnAksan")
        btn_tamamla.setMinimumHeight(46)
        btn_tamamla.setStyleSheet(
            f"QPushButton {{ background-color: {RENK['aksan']}; color: white; "
            f"font-size: 15px; font-weight: 700; border-radius: 8px; border: none; }}"
            f"QPushButton:hover {{ background-color: {RENK['aksan2']}; }}")
        btn_tamamla.clicked.connect(self._satisi_tamamla)
        alt_lay2.addWidget(btn_tamamla)

        btn_temizle = QPushButton("Sepeti Temizle")
        btn_temizle.setObjectName("BtnTehlike")
        btn_temizle.clicked.connect(self._sepet_temizle)
        alt_lay2.addWidget(btn_temizle)
        sag.addWidget(alt_kart)

        ana.addLayout(sag, 4)

        self._liste_yukle()

    # ── Liste ────────────────────────────────────────────────────────────
    def _liste_yukle(self):
        self._df = pd.DataFrame()
        try:
            conn = get_conn()
            self._df = pd.read_sql_query(
                "SELECT id, kategori, marka, yaygin_ad, ref1, fiyat, stok_miktari "
                "FROM stok WHERE stok_miktari > 0 ORDER BY marka, yaygin_ad", conn)
            conn.close()
        except: pass
        self._liste_filtrele()

    def _liste_filtrele(self):
        if self._df.empty:
            self.liste_tablo.setRowCount(0); return
        mask = pd.Series([True] * len(self._df), index=self._df.index)
        kat = self.cb_kat.currentText()
        ara = self.ara_txt.text().strip().lower()
        if kat != "Tüm Kategoriler":
            mask &= self._df["kategori"] == kat
        if ara:
            arama_str = (self._df["marka"].fillna("").str.lower() + " " +
                         self._df["yaygin_ad"].fillna("").str.lower() + " " +
                         self._df["kategori"].fillna("").str.lower())
            mask &= arama_str.str.contains(ara, regex=False, na=False)
        d = self._df[mask]
        _align = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        _c_bos = QColor(RENK["metin3"])
        self.liste_tablo.setUpdatesEnabled(False)
        try:
            self.liste_tablo.setRowCount(len(d))
            for i, (_, r) in enumerate(d.iterrows()):
                bos = r["stok_miktari"] <= 0
                for j, val in enumerate([str(r["id"]), r["kategori"],
                                          r["marka"], r["yaygin_ad"],
                                          str(r["stok_miktari"])]):
                    item = QTableWidgetItem(val)
                    item.setTextAlignment(_align)
                    if bos: item.setForeground(_c_bos)
                    self.liste_tablo.setItem(i, j, item)
        finally:
            self.liste_tablo.setUpdatesEnabled(True)

    def _listeden_ekle(self):
        rows = self.liste_tablo.selectionModel().selectedRows()
        if not rows: return
        stok_id = int(self.liste_tablo.item(rows[0].row(), 0).text())
        self._urun_sepete_ekle(stok_id)

    def _barkod_isle(self, deger):
        try:
            stok_id = int(deger)
        except ValueError:
            self._flash(f"⚠ Geçersiz barkod: {deger}", RENK["aksan"]); return
        self._urun_sepete_ekle(stok_id)

    def _urun_sepete_ekle(self, stok_id):
        if stok_id in self._sepet:
            # Adedi 1 artır
            widget, _ = self._sepet[stok_id]
            widget.sb_adet.setValue(widget.sb_adet.value() + 1)
            self._flash(f"✓ Adet artırıldı (ID: {stok_id})", RENK["mavi"])
            return
        urun = _stok_bul(stok_id)
        if not urun:
            self._flash(f"✗ ID {stok_id} bulunamadı!", RENK["aksan"]); return
        if urun["stok_miktari"] <= 0:
            self._flash(f"⚠ {urun['marka']} stokta yok!", RENK["sari"]); return

        try:
            fiyat = float(str(urun["fiyat"]).replace(",", "."))
        except: fiyat = 0.0

        satir = SepetSatiri(stok_id, urun["kategori"], urun["marka"],
                            urun["yaygin_ad"], urun["ref1"], fiyat)
        satir.silindi.connect(self._sepetten_cikar)
        satir.degisti.connect(self._toplami_guncelle)

        # Stretch'ten önce ekle
        self.sepet_lay.insertWidget(self.sepet_lay.count() - 1, satir)
        self._sepet[stok_id] = (satir, urun)
        self._flash(f"✓ {urun['marka']} / {urun['yaygin_ad']} eklendi", RENK["yesil"])
        self._toplami_guncelle()

    def _sepetten_cikar(self, stok_id):
        if stok_id in self._sepet:
            widget, _ = self._sepet.pop(stok_id)
            self.sepet_lay.removeWidget(widget)
            widget.deleteLater()
            self._toplami_guncelle()

    def _toplami_guncelle(self):
        toplam = sum(w.get_veri()[2] for w, _ in self._sepet.values())
        self.lbl_toplam.setText(f"₺{toplam:,.2f}")

    def _satisi_tamamla(self):
        if not self._sepet:
            QMessageBox.information(self, "Bilgi", "Sepet boş!"); return

        musteri = self.txt_musteri.text().strip()
        not_    = self.txt_not.text().strip()
        sheets  = get_sheets()

        satirlar = []
        for stok_id, (widget, urun) in self._sepet.items():
            adet, birim, toplam = widget.get_veri()
            # Stok kontrolü
            if urun["stok_miktari"] < adet:
                QMessageBox.warning(self, "Stok Yetersiz",
                    f"{urun['marka']} / {urun['yaygin_ad']}\n"
                    f"Stok: {urun['stok_miktari']}  İstenen: {adet}")
                return
            satirlar.append((stok_id, urun, adet, birim, toplam))

        # Onay
        toplam_tutar = sum(s[4] for s in satirlar)
        ozet = "\n".join(
            f"  • {s[1]['marka']} x{s[2]}  ₺{s[4]:,.2f}" for s in satirlar)
        cevap = QMessageBox.question(
            self, "Satışı Onayla",
            f"Satış kalemi: {len(satirlar)}\n{ozet}\n\nToplam: ₺{toplam_tutar:,.2f}\n\n"
            f"Onaylıyor musunuz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if cevap != QMessageBox.StandardButton.Yes: return

        # İşlem — DB kayıtları main thread'de, sheets sync arka planda
        for stok_id, urun, adet, birim, toplam in satirlar:
            yeni_stok = _stok_guncelle(stok_id, -adet)
            _hareket_kaydet("SATIS", stok_id, adet, birim, toplam,
                           musteri, "", 0, not_, yeni_stok)
            if sheets.aktif:
                t = _SheetsCallThread(
                    sheets.satis_ekle,
                    stok_id, urun["kategori"], urun["marka"],
                    urun["yaygin_ad"], urun["ref1"],
                    adet, birim, toplam, musteri, not_, yeni_stok)
                t.finished.connect(t.deleteLater)
                t.start()

        QMessageBox.information(self, "Tamamlandı",
            f"✓ Satış kaydedildi!\nToplam: ₺{toplam_tutar:,.2f}\n"
            f"{len(satirlar)} ürün stoktan düşüldü.")
        self._sepet_temizle()
        self._liste_yukle()

    def _sepet_temizle(self):
        for stok_id in list(self._sepet.keys()):
            widget, _ = self._sepet.pop(stok_id)
            self.sepet_lay.removeWidget(widget)
            widget.deleteLater()
        self._toplami_guncelle()

    def _flash(self, metin, renk):
        self.lbl_flash.setText(metin)
        self.lbl_flash.setStyleSheet(
            f"font-size: 12px; font-weight: 700; color: {renk};")
        QTimer.singleShot(3000, lambda: self.lbl_flash.setText(""))

    def guncelle(self):
        self._liste_yukle()


# ══════════════════════════════════════════════════════════════════════════
#  2. MAL GİRİŞİ
# ══════════════════════════════════════════════════════════════════════════
class MalGirisSayfasi(QWidget):

    def __init__(self):
        super().__init__()
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(14)

        lbl = QLabel("GELEN MAL GİRİŞİ")
        lbl.setStyleSheet(
            f"font-size: 10px; font-weight: 700; letter-spacing: 2px; color: {RENK['metin2']};")
        lay.addWidget(lbl)

        # Tab: Barkod / Toplu CSV
        tab = QTabWidget()
        tab.setDocumentMode(True)
        tab.addTab(self._barkod_sayfasi(), "  Barkod ile Tek Tek  ")
        tab.addTab(self._csv_sayfasi(),    "  Toplu CSV ile  ")
        lay.addWidget(tab)

    def _barkod_sayfasi(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        # Barkod giriş kartı
        kart = QFrame()
        kart.setObjectName("Kart")
        kart.setStyleSheet(
            f"QFrame#Kart {{ background: {RENK['yuzey']}; border-radius: 10px; "
            f"border: 1px solid {RENK['cizgi']}; }}")
        klay = QVBoxLayout(kart)
        klay.setContentsMargins(16, 14, 16, 14)
        klay.setSpacing(10)

        lbl_bk = QLabel("BARKOD / ID OKUT")
        lbl_bk.setStyleSheet(
            f"font-size: 10px; font-weight: 700; letter-spacing: 1.5px; color: {RENK['metin2']};")
        klay.addWidget(lbl_bk)

        self.barkod_mg = BarkodInput("Stok ID veya barkod okutun...")
        self.barkod_mg.barkod_okundu.connect(self._barkod_isle_giris)
        klay.addWidget(self.barkod_mg)

        # Ürün detay alanı
        self.mg_urun_lbl = QLabel("—")
        self.mg_urun_lbl.setStyleSheet(
            f"font-size: 14px; font-weight: 700; color: {RENK['metin']};")
        klay.addWidget(self.mg_urun_lbl)
        lay.addWidget(kart)

        # Giriş formu
        form_kart = QFrame()
        form_kart.setObjectName("Kart")
        form_kart.setStyleSheet(
            f"QFrame#Kart {{ background: {RENK['yuzey']}; border-radius: 10px; "
            f"border: 1px solid {RENK['cizgi']}; }}")
        flay = QVBoxLayout(form_kart)
        flay.setContentsMargins(16, 14, 16, 14)
        flay.setSpacing(10)

        self._mg_stok_id = None

        def satir(etiket, widget):
            row = QHBoxLayout()
            l = QLabel(etiket)
            l.setFixedWidth(130)
            l.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {RENK['metin2']};")
            row.addWidget(l)
            row.addWidget(widget)
            flay.addLayout(row)
            return widget

        self.mg_adet = satir("Giren Adet:", QSpinBox())
        self.mg_adet.setRange(1, 99999)
        self.mg_adet.setValue(1)
        self.mg_adet.setMinimumHeight(36)

        self.mg_fiyat = satir("Giriş Fiyatı (₺):", QDoubleSpinBox())
        self.mg_fiyat.setRange(0, 9_999_999)
        self.mg_fiyat.setDecimals(2)
        self.mg_fiyat.setMinimumHeight(36)

        self.mg_tedarikci = satir("Tedarikçi:", QLineEdit())
        self.mg_tedarikci.setPlaceholderText("Opsiyonel")
        self.mg_tedarikci.setMinimumHeight(36)

        self.mg_not = satir("Not:", QLineEdit())
        self.mg_not.setMinimumHeight(36)

        self.mg_flash = QLabel("")
        self.mg_flash.setStyleSheet("font-size: 12px; font-weight: 700;")
        flay.addWidget(self.mg_flash)

        btn_kaydet = QPushButton("✓  Mal Girişini Kaydet")
        btn_kaydet.setObjectName("BtnBasarili")
        btn_kaydet.setMinimumHeight(42)
        btn_kaydet.clicked.connect(self._mg_kaydet)
        flay.addWidget(btn_kaydet)

        lay.addWidget(form_kart)
        lay.addStretch()
        return w

    def _barkod_isle_giris(self, deger):
        try:
            stok_id = int(deger)
        except ValueError:
            self._mg_flash_goster(f"⚠ Geçersiz: {deger}", RENK["aksan"]); return
        urun = _stok_bul(stok_id)
        if not urun:
            self._mg_flash_goster(f"✗ ID {stok_id} bulunamadı!", RENK["aksan"]); return
        self._mg_stok_id = stok_id
        self.mg_urun_lbl.setText(
            f"✓  {urun['marka']}  /  {urun['yaygin_ad']}  "
            f"(Mevcut stok: {urun['stok_miktari']})")
        self.mg_urun_lbl.setStyleSheet(
            f"font-size: 14px; font-weight: 700; color: {RENK['yesil']};")

    def _mg_kaydet(self):
        if not self._mg_stok_id:
            QMessageBox.warning(self, "Uyarı", "Önce barkod okutun!"); return
        urun = _stok_bul(self._mg_stok_id)
        if not urun: return
        adet      = self.mg_adet.value()
        fiyat     = self.mg_fiyat.value()
        tedarikci = self.mg_tedarikci.text().strip()
        not_      = self.mg_not.text().strip()

        yeni_stok = _stok_guncelle(self._mg_stok_id, +adet)
        _hareket_kaydet("MAL_GIRIS", self._mg_stok_id, adet,
                        0, 0, "", tedarikci, fiyat, not_, yeni_stok)

        sheets = get_sheets()
        if sheets.aktif:
            t = _SheetsCallThread(
                sheets.mal_giris_ekle,
                self._mg_stok_id, urun["kategori"], urun["marka"],
                urun["yaygin_ad"], adet, fiyat, tedarikci, not_, yeni_stok)
            t.finished.connect(t.deleteLater)
            t.start()

        self._mg_flash_goster(
            f"✓ {adet} adet girişi kaydedildi. Yeni stok: {yeni_stok}",
            RENK["yesil"])
        self._mg_stok_id = None
        self.mg_urun_lbl.setText("—")
        self.mg_urun_lbl.setStyleSheet(
            f"font-size: 14px; font-weight: 700; color: {RENK['metin']};")
        self.mg_adet.setValue(1)
        self.mg_fiyat.setValue(0)
        self.mg_tedarikci.clear()
        self.mg_not.clear()

    def _mg_flash_goster(self, metin, renk):
        self.mg_flash.setText(metin)
        self.mg_flash.setStyleSheet(
            f"font-size: 12px; font-weight: 700; color: {renk};")
        QTimer.singleShot(4000, lambda: self.mg_flash.setText(""))

    def _csv_sayfasi(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(14)

        aciklama = QLabel(
            "Toplu mal girişi için aşağıdaki şablonu indirin, doldurun ve yükleyin.\n"
            "Şablon sütunları: Stok ID, Giren Adet, Giriş Fiyatı, Tedarikçi, Not")
        aciklama.setWordWrap(True)
        aciklama.setStyleSheet(f"color: {RENK['metin2']}; font-size: 13px;")
        lay.addWidget(aciklama)

        btn_sablon = QPushButton("⬇  Mal Girişi Şablonunu İndir")
        btn_sablon.setObjectName("BtnIkincil")
        btn_sablon.setFixedWidth(260)
        btn_sablon.clicked.connect(self._sablon_indir)
        lay.addWidget(btn_sablon)

        lay.addWidget(AyiriciCizgi())

        btn_yukle = QPushButton("⬆  CSV Yükle ve İşle")
        btn_yukle.setObjectName("BtnAksan")
        btn_yukle.setFixedWidth(200)
        btn_yukle.clicked.connect(self._csv_yukle)
        lay.addWidget(btn_yukle)

        self.csv_log = QTextEdit()
        self.csv_log.setReadOnly(True)
        self.csv_log.setPlaceholderText("İşlem sonuçları burada görünecek...")
        self.csv_log.setStyleSheet(
            f"background: {RENK['yuzey2']}; border: 1px solid {RENK['cizgi']}; "
            f"border-radius: 8px; font-family: monospace; font-size: 12px;")
        lay.addWidget(self.csv_log, 1)
        return w

    def _sablon_indir(self):
        kaydet, _ = QFileDialog.getSaveFileName(
            self, "Şablonu Kaydet", "mal_giris_sablonu.csv",
            "CSV (*.csv)", options=QFileDialog.Option.DontUseNativeDialog)
        if not kaydet: return
        import csv
        with open(kaydet, "w", newline="", encoding="utf-8-sig") as f:
            cw = csv.writer(f)
            cw.writerow(["Stok ID", "Giren Adet", "Giriş Fiyatı", "Tedarikçi", "Not"])
            cw.writerow([101, 5, 150.00, "Örnek Tedarikçi", "Fatura No: 2024/001"])
        QMessageBox.information(self, "Tamam", f"Şablon kaydedildi:\n{kaydet}")

    def _csv_yukle(self):
        dosya, _ = QFileDialog.getOpenFileName(
            self, "CSV Seç", "", "CSV (*.csv)",
            options=QFileDialog.Option.DontUseNativeDialog)
        if not dosya: return
        try:
            df = pd.read_csv(dosya, encoding="utf-8-sig")
        except:
            try: df = pd.read_csv(dosya, encoding="latin-1")
            except Exception as e:
                self.csv_log.setText(f"HATA: {e}"); return

        log = []
        sheets = get_sheets()
        for _, r in df.iterrows():
            try:
                sid       = int(r.get("Stok ID", 0))
                adet      = int(r.get("Giren Adet", 1))
                fiyat     = float(str(r.get("Giriş Fiyatı", 0)).replace(",", "."))
                tedarikci = str(r.get("Tedarikçi", "")).strip()
                not_      = str(r.get("Not", "")).strip()
                urun = _stok_bul(sid)
                if not urun:
                    log.append(f"✗ ID {sid} bulunamadı — atlandı")
                    continue
                yeni = _stok_guncelle(sid, +adet)
                _hareket_kaydet("MAL_GIRIS", sid, adet, 0, 0,
                               "", tedarikci, fiyat, not_, yeni)
                if sheets.aktif:
                    sheets.mal_giris_ekle(sid, urun["kategori"], urun["marka"],
                                         urun["yaygin_ad"], adet, fiyat,
                                         tedarikci, not_, yeni)
                log.append(
                    f"✓ ID {sid}  {urun['marka']}  +{adet} adet  → yeni stok: {yeni}")
            except Exception as e:
                log.append(f"✗ Satır hatası: {e}")
        self.csv_log.setText("\n".join(log))

    def guncelle(self):
        pass


# ══════════════════════════════════════════════════════════════════════════
#  3. HAREKET GEÇMİŞİ
# ══════════════════════════════════════════════════════════════════════════
class HareketGecmisiSayfasi(QWidget):

    def __init__(self):
        super().__init__()
        self._build()
        self.yukle()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(12)

        # Filtreler
        fil_lay = QHBoxLayout()
        fil_lay.setSpacing(10)

        self.cb_tip = QComboBox()
        self.cb_tip.setMinimumHeight(36)
        self.cb_tip.addItems(["Tüm Hareketler", "SATIŞ", "MAL GİRİŞİ"])
        self.cb_tip.currentIndexChanged.connect(self.yukle)

        self.ara = QLineEdit()
        self.ara.setPlaceholderText("Marka, müşteri, not...")
        self.ara.setMinimumHeight(36)
        self.ara.textChanged.connect(self.yukle)

        self.cb_kat = QComboBox()
        self.cb_kat.setMinimumHeight(36)
        self.cb_kat.addItems(["Tüm Kategoriler", "Beyin", "ABS", "Plastik"])
        self.cb_kat.currentIndexChanged.connect(self.yukle)

        fil_lay.addWidget(QLabel("Tür:"))
        fil_lay.addWidget(self.cb_tip)
        fil_lay.addWidget(QLabel("Kategori:"))
        fil_lay.addWidget(self.cb_kat)
        fil_lay.addWidget(self.ara, 2)
        lay.addLayout(fil_lay)

        # Özet stat kartları
        stat_lay = QHBoxLayout()
        stat_lay.setSpacing(12)
        self.s_satis   = StatKart("Bugün Satış",      "0", RENK["aksan"])
        self.s_giris   = StatKart("Bugün Mal Girişi", "0", RENK["yesil"])
        self.s_ciro    = StatKart("Bugün Ciro",       "₺0", RENK["mavi"])
        for s in [self.s_satis, self.s_giris, self.s_ciro]:
            stat_lay.addWidget(s)
        stat_lay.addStretch()
        lay.addLayout(stat_lay)

        # Tablo
        self.tablo = QTableWidget()
        self.tablo.setColumnCount(10)
        self.tablo.setHorizontalHeaderLabels([
            "ZAMAN", "TİP", "ID", "KATEGORİ", "MARKA",
            "YAYGIN AD", "ADET", "BİRİM FİYAT", "TUTAR", "MÜŞTERİ/TEDARİKÇİ"
        ])
        self.tablo.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tablo.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tablo.verticalHeader().setVisible(False)
        self.tablo.setAlternatingRowColors(True)
        hh = self.tablo.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tablo.verticalHeader().setDefaultSectionSize(32)
        lay.addWidget(self.tablo, 1)

        # Alt çubuk
        alt_lay = QHBoxLayout()
        self.lbl_sayac = QLabel("")
        self.lbl_sayac.setStyleSheet(f"color: {RENK['metin2']}; font-size: 12px;")
        btn_export = QPushButton("⬇  CSV İndir")
        btn_export.setObjectName("BtnIkincil")
        btn_export.clicked.connect(self._export_csv)
        alt_lay.addWidget(self.lbl_sayac)
        alt_lay.addStretch()
        alt_lay.addWidget(btn_export)
        lay.addLayout(alt_lay)

    def yukle(self):
        conn = get_conn()
        tip = self.cb_tip.currentText()
        kat = self.cb_kat.currentText()
        ara = self.ara.text().strip().lower()

        tip_map = {"SATIŞ": "SATIS", "MAL GİRİŞİ": "MAL_GIRIS"}
        sql = """
            SELECT h.*, s.kategori, s.marka, s.yaygin_ad, s.ref1
            FROM hareket h
            LEFT JOIN stok s ON s.id = h.stok_id
            WHERE 1=1
        """
        params = []
        if tip in tip_map:
            sql += " AND h.hareket_tipi=?"; params.append(tip_map[tip])
        if kat != "Tüm Kategoriler":
            sql += " AND s.kategori=?"; params.append(kat)
        sql += " ORDER BY h.zaman DESC LIMIT 500"

        rows = conn.execute(sql, params).fetchall()

        # Bugün özet
        bugun = datetime.now().strftime("%Y-%m-%d")
        ozet = conn.execute("""
            SELECT hareket_tipi, COUNT(*) as n, SUM(toplam_tutar) as ciro
            FROM hareket WHERE date(zaman)=?
            GROUP BY hareket_tipi
        """, (bugun,)).fetchall()
        conn.close()

        satis_n = giris_n = 0; ciro = 0.0
        for o in ozet:
            if o["hareket_tipi"] == "SATIS":
                satis_n = o["n"]; ciro = o["ciro"] or 0.0
            elif o["hareket_tipi"] == "MAL_GIRIS":
                giris_n = o["n"]
        self.s_satis.set_deger(satis_n)
        self.s_giris.set_deger(giris_n)
        self.s_ciro.set_deger(f"₺{ciro:,.0f}")

        # Arama filtresi
        if ara:
            rows = [r for r in rows if ara in " ".join([
                str(r["marka"] or ""), str(r["yaygin_ad"] or ""),
                str(r["musteri_adi"] or ""), str(r["notlar"] or ""),
                str(r["tedarikci"] or "")
            ]).lower()]

        tip_renk = {"SATIS": RENK["aksan"], "MAL_GIRIS": RENK["yesil"], "DUZELTME": RENK["mavi"]}
        tip_lbl  = {"SATIS": "SATIŞ", "MAL_GIRIS": "GİRİŞ", "DUZELTME": "DÜZELTME"}
        _align   = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        _bold    = QFont("", -1, QFont.Weight.Bold)

        self.tablo.setUpdatesEnabled(False)
        try:
            self.tablo.setRowCount(len(rows))
            for i, r in enumerate(rows):
                musteri_ted = r["musteri_adi"] or r["tedarikci"] or "-"
                tutar_str = (f"₺{r['toplam_tutar']:,.2f}"
                            if r["toplam_tutar"] else f"₺{r['giris_fiyati']:,.2f}")
                vals = [
                    str(r["zaman"] or "")[:16],
                    tip_lbl.get(r["hareket_tipi"], r["hareket_tipi"]),
                    str(r["stok_id"] or ""),
                    r["kategori"] or "-",
                    r["marka"] or "-",
                    r["yaygin_ad"] or "-",
                    str(r["adet"]),
                    f"₺{r['birim_fiyat']:,.2f}" if r["birim_fiyat"] else "-",
                    tutar_str,
                    musteri_ted,
                ]
                renk = QColor(tip_renk.get(r["hareket_tipi"], RENK["metin"]))
                for j, val in enumerate(vals):
                    item = QTableWidgetItem(val)
                    item.setTextAlignment(_align)
                    if j == 1:
                        item.setForeground(renk)
                        item.setFont(_bold)
                    self.tablo.setItem(i, j, item)
        finally:
            self.tablo.setUpdatesEnabled(True)

        self.lbl_sayac.setText(f"{len(rows)} kayıt")

    def _export_csv(self):
        kaydet, _ = QFileDialog.getSaveFileName(
            self, "CSV Kaydet",
            f"hareketler_{datetime.now().strftime('%Y%m%d')}.csv",
            "CSV (*.csv)", options=QFileDialog.Option.DontUseNativeDialog)
        if not kaydet: return
        conn = get_conn()
        df = pd.read_sql_query("""
            SELECT h.zaman, h.hareket_tipi, h.stok_id,
                   s.kategori, s.marka, s.yaygin_ad,
                   h.adet, h.birim_fiyat, h.toplam_tutar,
                   h.musteri_adi, h.tedarikci, h.giris_fiyati,
                   h.notlar, h.stok_sonrasi
            FROM hareket h LEFT JOIN stok s ON s.id = h.stok_id
            ORDER BY h.zaman DESC
        """, conn)
        conn.close()
        df.to_csv(kaydet, index=False, encoding="utf-8-sig")
        QMessageBox.information(self, "Tamam", f"✓ {len(df)} kayıt dışa aktarıldı.")

    def guncelle(self):
        self.yukle()


# ══════════════════════════════════════════════════════════════════════════
#  ANA HAREKETLER SAYFASI
# ══════════════════════════════════════════════════════════════════════════
class HareketlerSayfasi(QWidget):

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Sheets durum bandı
        self.sheets_band = QFrame()
        self.sheets_band.setFixedHeight(30)
        bl = QHBoxLayout(self.sheets_band)
        bl.setContentsMargins(20, 0, 20, 0)
        self.lbl_sheets = QLabel("")
        self.lbl_sheets.setStyleSheet("font-size: 11px; font-weight: 600;")
        bl.addWidget(self.lbl_sheets)
        bl.addStretch()
        lay.addWidget(self.sheets_band)
        lay.addWidget(AyiriciCizgi())

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        self.satis_s  = HizliSatisSayfasi()
        self.giris_s  = MalGirisSayfasi()
        self.gecmis_s = HareketGecmisiSayfasi()

        self.tabs.addTab(self.satis_s,  "  🛒  Hızlı Satış  ")
        self.tabs.addTab(self.giris_s,  "  📦  Mal Girişi  ")
        self.tabs.addTab(self.gecmis_s, "  📋  Hareket Geçmişi  ")
        self.tabs.currentChanged.connect(self._sekme_degisti)
        lay.addWidget(self.tabs, 1)

        self._sheets_goster()

    def _sheets_goster(self):
        sheets = get_sheets()
        if sheets.aktif and not sheets.hata_msg:
            self.sheets_band.setStyleSheet(f"background-color: {RENK['yesil_bg']};")
            self.lbl_sheets.setText("● Sheets bağlı — satış ve girişler anlık senkronize edilir")
            self.lbl_sheets.setStyleSheet(
                f"font-size: 11px; font-weight: 600; color: {RENK['yesil']};")
        else:
            self.sheets_band.setStyleSheet(f"background-color: {RENK['yuzey2']};")
            self.lbl_sheets.setText("○ Sheets bağlı değil — yalnızca yerel kayıt")
            self.lbl_sheets.setStyleSheet(
                f"font-size: 11px; font-weight: 600; color: {RENK['metin3']};")

    def _sekme_degisti(self, idx):
        if idx == 0: self.satis_s.guncelle()
        elif idx == 1: self.giris_s.guncelle()
        elif idx == 2: self.gecmis_s.guncelle()
        self._sheets_goster()
