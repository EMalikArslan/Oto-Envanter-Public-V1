"""
modules/musteri.py
──────────────────
Müşteri Listesi — 2 sekme:

  1. Müşteri Listesi  — arama, filtreleme, borç durumu
  2. Borç / Tahsilat  — borç ekle, ödeme al, geçmiş
"""

import sqlite3
import pandas as pd
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QLabel, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFrame, QComboBox,
    QMessageBox, QDialog, QTextEdit, QDoubleSpinBox, QCheckBox,
    QScrollArea, QGridLayout, QSpinBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont

from core.database import get_conn, v
from core.tema import RENK
from core.widgets import StatKart, AyiriciCizgi

# Türkiye illeri (kısaltılmış)
ILLER = sorted([
    "Adana","Adıyaman","Afyonkarahisar","Ağrı","Amasya","Ankara","Antalya",
    "Artvin","Aydın","Balıkesir","Bilecik","Bingöl","Bitlis","Bolu",
    "Burdur","Bursa","Çanakkale","Çankırı","Çorum","Denizli","Diyarbakır",
    "Edirne","Elazığ","Erzincan","Erzurum","Eskişehir","Gaziantep","Giresun",
    "Gümüşhane","Hakkari","Hatay","Isparta","Mersin","İstanbul","İzmir",
    "Kars","Kastamonu","Kayseri","Kırklareli","Kırşehir","Kocaeli","Konya",
    "Kütahya","Malatya","Manisa","Kahramanmaraş","Mardin","Muğla","Muş",
    "Nevşehir","Niğde","Ordu","Rize","Sakarya","Samsun","Siirt","Sinop",
    "Sivas","Tekirdağ","Tokat","Trabzon","Tunceli","Şanlıurfa","Uşak",
    "Van","Yozgat","Zonguldak","Aksaray","Bayburt","Karaman","Kırıkkale",
    "Batman","Şırnak","Bartın","Ardahan","Iğdır","Yalova","Karabük",
    "Kilis","Osmaniye","Düzce"
])

URUN_GRUPLARI = ["Beyin", "ABS", "Plastik"]


# ══════════════════════════════════════════════════════════════════════════
#  Müşteri Ekle / Düzenle Dialog
# ══════════════════════════════════════════════════════════════════════════
class MusteriDialog(QDialog):
    def __init__(self, parent=None, kayit=None):
        super().__init__(parent)
        self.setWindowTitle("Müşteri Ekle" if not kayit else "Müşteri Düzenle")
        self.setMinimumWidth(500)
        self.setMinimumHeight(520)
        self.setStyleSheet(
            f"background-color: {RENK['yuzey']}; color: {RENK['metin']};")

        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.setContentsMargins(24, 24, 24, 24)

        lbl = QLabel("Müşteri Bilgileri")
        lbl.setStyleSheet("font-size: 16px; font-weight: 700;")
        lay.addWidget(lbl)
        lay.addWidget(AyiriciCizgi())

        def satir(et, w):
            row = QHBoxLayout()
            l = QLabel(et); l.setFixedWidth(140)
            l.setStyleSheet(
                f"font-size: 12px; font-weight: 600; color: {RENK['metin2']};")
            row.addWidget(l); row.addWidget(w)
            lay.addLayout(row)
            return w

        self.dukkan  = satir("Dükkan Adı: *", QLineEdit(kayit["dukkan_adi"] if kayit else ""))
        self.dukkan.setMinimumHeight(36)

        self.yetkili = satir("Yetkili Adı:", QLineEdit(kayit["yetkili_adi"] if kayit and kayit["yetkili_adi"] != "-" else ""))
        self.yetkili.setMinimumHeight(36)

        # İl seçici
        self.cb_il = QComboBox()
        self.cb_il.setEditable(True)
        self.cb_il.addItem("")
        self.cb_il.addItems(ILLER)
        self.cb_il.setMinimumHeight(36)
        if kayit and kayit["il"] != "-":
            self.cb_il.setCurrentText(kayit["il"])
        satir("İl:", self.cb_il)

        self.ilce = satir("İlçe:", QLineEdit(kayit["ilce"] if kayit and kayit["ilce"] != "-" else ""))
        self.ilce.setMinimumHeight(36)

        self.adres = satir("Adres:", QLineEdit(kayit["adres"] if kayit and kayit["adres"] != "-" else ""))
        self.adres.setMinimumHeight(36)

        self.telefon = satir("Telefon:", QLineEdit(kayit["telefon"] if kayit and kayit["telefon"] != "-" else ""))
        self.telefon.setMinimumHeight(36)
        self.telefon.setPlaceholderText("0532 xxx xx xx")

        self.email = satir("E-posta:", QLineEdit(kayit["email"] if kayit and kayit["email"] != "-" else ""))
        self.email.setMinimumHeight(36)

        # Ürün grupları
        lay.addWidget(QLabel("Ana Ürün Grupları:"))
        grp_lay = QHBoxLayout()
        mevcut_gruplar = (kayit["urun_gruplari"] or "").split(",") if kayit else []
        self.grp_checks = {}
        for g in URUN_GRUPLARI:
            cb = QCheckBox(g)
            cb.setChecked(g in mevcut_gruplar)
            grp_lay.addWidget(cb)
            self.grp_checks[g] = cb
        grp_lay.addStretch()
        lay.addLayout(grp_lay)

        lay.addWidget(QLabel("Notlar:"))
        self.notlar = QTextEdit(kayit["notlar"] if kayit else "")
        self.notlar.setMaximumHeight(70)
        self.notlar.setPlaceholderText("Serbest not alanı...")
        lay.addWidget(self.notlar)

        lay.addWidget(AyiriciCizgi())
        btn_lay = QHBoxLayout()
        bi = QPushButton("İptal"); bi.setObjectName("BtnIkincil")
        bi.clicked.connect(self.reject)
        bk = QPushButton("Kaydet"); bk.setObjectName("BtnAksan")
        bk.clicked.connect(self._kaydet)
        btn_lay.addWidget(bi); btn_lay.addWidget(bk)
        lay.addLayout(btn_lay)

    def _kaydet(self):
        if not self.dukkan.text().strip():
            QMessageBox.warning(self, "Uyarı", "Dükkan adı boş olamaz!"); return
        self.accept()

    def get_veri(self):
        gruplar = ",".join(g for g, cb in self.grp_checks.items() if cb.isChecked())
        return {
            "dukkan_adi":   self.dukkan.text().strip(),
            "yetkili_adi":  self.yetkili.text().strip() or "-",
            "il":           self.cb_il.currentText().strip() or "-",
            "ilce":         self.ilce.text().strip() or "-",
            "adres":        self.adres.text().strip() or "-",
            "telefon":      self.telefon.text().strip() or "-",
            "email":        self.email.text().strip() or "-",
            "urun_gruplari": gruplar or "-",
            "notlar":       self.notlar.toPlainText().strip(),
        }


# ══════════════════════════════════════════════════════════════════════════
#  Borç İşlem Dialog
# ══════════════════════════════════════════════════════════════════════════
class BorcDialog(QDialog):
    def __init__(self, parent, musteri_adi, mevcut_borc=0.0):
        super().__init__(parent)
        self.setWindowTitle("Borç / Ödeme Kaydı")
        self.setMinimumWidth(360)
        self.setStyleSheet(
            f"background-color: {RENK['yuzey']}; color: {RENK['metin']};")
        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        lay.setContentsMargins(24, 24, 24, 24)

        lbl = QLabel(f"Müşteri: {musteri_adi}")
        lbl.setStyleSheet("font-size: 15px; font-weight: 700;")
        lay.addWidget(lbl)

        mevcut_lbl = QLabel(f"Mevcut borç: ₺{mevcut_borc:,.2f}")
        renk = RENK["aksan"] if mevcut_borc > 0 else RENK["yesil"]
        mevcut_lbl.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {renk};")
        lay.addWidget(mevcut_lbl)
        lay.addWidget(AyiriciCizgi())

        # İşlem tipi
        tip_lay = QHBoxLayout()
        self.rb_borc = QPushButton("Borç Ekle")
        self.rb_borc.setCheckable(True)
        self.rb_borc.setChecked(True)
        self.rb_odeme = QPushButton("Ödeme Al")
        self.rb_odeme.setCheckable(True)

        def _tip_sec(btn, diger):
            btn.setChecked(True)
            diger.setChecked(False)
            btn.setStyleSheet(
                f"background: {RENK['metin']}; color: white; "
                f"border-radius: 6px; padding: 8px; font-weight: 700; border: none;")
            diger.setStyleSheet(
                f"background: {RENK['yuzey2']}; color: {RENK['metin2']}; "
                f"border-radius: 6px; padding: 8px; font-weight: 600; "
                f"border: 1.5px solid {RENK['cizgi']};")

        self.rb_borc.clicked.connect(lambda: _tip_sec(self.rb_borc, self.rb_odeme))
        self.rb_odeme.clicked.connect(lambda: _tip_sec(self.rb_odeme, self.rb_borc))
        tip_lay.addWidget(self.rb_borc)
        tip_lay.addWidget(self.rb_odeme)
        lay.addLayout(tip_lay)
        _tip_sec(self.rb_borc, self.rb_odeme)

        # Tutar
        t_lay = QHBoxLayout()
        t_lbl = QLabel("Tutar (₺):")
        t_lbl.setFixedWidth(100)
        self.sb_tutar = QDoubleSpinBox()
        self.sb_tutar.setRange(0.01, 9_999_999)
        self.sb_tutar.setDecimals(2)
        self.sb_tutar.setMinimumHeight(40)
        self.sb_tutar.setValue(0)
        t_lay.addWidget(t_lbl)
        t_lay.addWidget(self.sb_tutar)
        lay.addLayout(t_lay)

        n_lay = QHBoxLayout()
        n_lbl = QLabel("Not:")
        n_lbl.setFixedWidth(100)
        self.txt_not = QLineEdit()
        self.txt_not.setMinimumHeight(36)
        self.txt_not.setPlaceholderText("opsiyonel")
        n_lay.addWidget(n_lbl)
        n_lay.addWidget(self.txt_not)
        lay.addLayout(n_lay)

        lay.addWidget(AyiriciCizgi())
        btn_lay = QHBoxLayout()
        bi = QPushButton("İptal"); bi.setObjectName("BtnIkincil")
        bi.clicked.connect(self.reject)
        bk = QPushButton("Kaydet"); bk.setObjectName("BtnAksan")
        bk.clicked.connect(self.accept)
        btn_lay.addWidget(bi); btn_lay.addWidget(bk)
        lay.addLayout(btn_lay)

    def get_veri(self):
        tip   = "BORC" if self.rb_borc.isChecked() else "ODEME"
        tutar = self.sb_tutar.value()
        delta = tutar if tip == "BORC" else -tutar
        return tip, tutar, delta, self.txt_not.text().strip()


# ══════════════════════════════════════════════════════════════════════════
#  1. MÜŞTERİ LİSTESİ
# ══════════════════════════════════════════════════════════════════════════
class MusteriListesiSayfasi(QWidget):

    def __init__(self, on_musteri_sec=None):
        super().__init__()
        self.on_musteri_sec = on_musteri_sec
        self._df = pd.DataFrame()
        self._build()
        self.yukle()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)

        # Stat kartları
        stat_lay = QHBoxLayout()
        stat_lay.setSpacing(12)
        self.s_toplam  = StatKart("Toplam Müşteri", "—", RENK["metin2"])
        self.s_borclu  = StatKart("Borçlu",          "—", RENK["aksan"])
        self.s_top_borc= StatKart("Toplam Alacak",   "₺—", RENK["mavi"])
        for s in [self.s_toplam, self.s_borclu, self.s_top_borc]:
            stat_lay.addWidget(s)
        stat_lay.addStretch()
        lay.addLayout(stat_lay)

        # Filtreler
        fil = QHBoxLayout()
        fil.setSpacing(10)
        self.ara = QLineEdit()
        self.ara.setPlaceholderText("Dükkan adı, il, telefon ara...")
        self.ara.setMinimumHeight(38)
        self.ara.textChanged.connect(self._filtrele)

        self.cb_il = QComboBox()
        self.cb_il.setMinimumHeight(38)
        self.cb_il.addItem("Tüm İller")
        self.cb_il.addItems(ILLER)
        self.cb_il.currentIndexChanged.connect(self._filtrele)

        self.cb_borc = QComboBox()
        self.cb_borc.setMinimumHeight(38)
        self.cb_borc.addItems(["Tüm Müşteriler", "Borçlular", "Borçsuzlar"])
        self.cb_borc.currentIndexChanged.connect(self._filtrele)

        self.cb_grup = QComboBox()
        self.cb_grup.setMinimumHeight(38)
        self.cb_grup.addItems(["Tüm Gruplar"] + URUN_GRUPLARI)
        self.cb_grup.currentIndexChanged.connect(self._filtrele)

        fil.addWidget(self.ara, 3)
        fil.addWidget(self.cb_il, 1)
        fil.addWidget(self.cb_borc, 1)
        fil.addWidget(self.cb_grup, 1)
        lay.addLayout(fil)

        # Tablo
        self.tablo = QTableWidget()
        self.tablo.setColumnCount(9)
        self.tablo.setHorizontalHeaderLabels([
            "ID", "DÜKKAN ADI", "YETKİLİ", "İL", "İLÇE",
            "TELEFON", "ÜRÜN GRUPLARI", "BORÇ", "NOT"
        ])
        self.tablo.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tablo.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tablo.verticalHeader().setVisible(False)
        self.tablo.setAlternatingRowColors(True)
        self.tablo.doubleClicked.connect(self._duzenle)
        hh = self.tablo.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        self.tablo.verticalHeader().setDefaultSectionSize(34)
        lay.addWidget(self.tablo, 1)

        # Alt butonlar
        alt = QHBoxLayout()
        btn_ekle  = QPushButton("+ Müşteri Ekle"); btn_ekle.setObjectName("BtnAksan")
        btn_ekle.clicked.connect(self._ekle)
        btn_sil   = QPushButton("Sil"); btn_sil.setObjectName("BtnTehlike")
        btn_sil.clicked.connect(self._sil)
        btn_borc  = QPushButton("Borç / Ödeme"); btn_borc.setObjectName("BtnIkincil")
        btn_borc.clicked.connect(self._borc_isle)
        self.lbl_sec = QLabel("")
        self.lbl_sec.setStyleSheet(f"color: {RENK['metin2']}; font-size: 12px;")

        alt.addWidget(btn_ekle)
        alt.addWidget(btn_borc)
        alt.addWidget(btn_sil)
        alt.addStretch()
        alt.addWidget(self.lbl_sec)
        lay.addLayout(alt)

        self.tablo.selectionModel().selectionChanged.connect(
            lambda: self.lbl_sec.setText(
                f"{len(self.tablo.selectionModel().selectedRows())} seçili"))

    def yukle(self):
        conn = get_conn()
        self._df = pd.read_sql_query(
            "SELECT * FROM musteri ORDER BY dukkan_adi", conn)
        conn.close()
        n    = len(self._df)
        borclu = (self._df["borc"] > 0).sum() if n else 0
        top_borc = self._df["borc"].sum() if n else 0
        self.s_toplam.set_deger(n)
        self.s_borclu.set_deger(borclu)
        self.s_top_borc.set_deger(f"₺{top_borc:,.2f}")
        self._filtrele()

    def _filtrele(self):
        if self._df.empty:
            self.tablo.setRowCount(0); return
        d = self._df.copy()
        ara  = self.ara.text().strip().lower()
        il   = self.cb_il.currentText()
        borc = self.cb_borc.currentText()
        grup = self.cb_grup.currentText()

        if il != "Tüm İller":
            d = d[d["il"] == il]
        if borc == "Borçlular":
            d = d[d["borc"] > 0]
        elif borc == "Borçsuzlar":
            d = d[d["borc"] <= 0]
        if grup != "Tüm Gruplar":
            d = d[d["urun_gruplari"].str.contains(grup, na=False)]
        if ara:
            mask = d.astype(str).apply(
                lambda c: c.str.lower().str.contains(ara, na=False)).any(axis=1)
            d = d[mask]

        self.tablo.setRowCount(len(d))
        for i, (_, r) in enumerate(d.iterrows()):
            vals = [
                str(int(r["id"])), r["dukkan_adi"], r["yetkili_adi"],
                r["il"], r["ilce"], r["telefon"], r["urun_gruplari"],
                f"₺{r['borc']:,.2f}", r["notlar"][:30] if r["notlar"] else ""
            ]
            for j, val in enumerate(vals):
                item = QTableWidgetItem(val)
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                if j == 7:
                    borc_val = r["borc"]
                    if borc_val > 0:
                        item.setForeground(QColor(RENK["aksan"]))
                        item.setFont(QFont("", -1, QFont.Weight.Bold))
                    else:
                        item.setForeground(QColor(RENK["yesil"]))
                self.tablo.setItem(i, j, item)

    def _get_secili_id(self):
        rows = self.tablo.selectionModel().selectedRows()
        if not rows: return None
        return int(self.tablo.item(rows[0].row(), 0).text())

    def _ekle(self):
        dlg = MusteriDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted: return
        d = dlg.get_veri()
        conn = get_conn()
        conn.execute("""INSERT INTO musteri
            (dukkan_adi,yetkili_adi,il,ilce,adres,telefon,email,urun_gruplari,notlar)
            VALUES (:dukkan_adi,:yetkili_adi,:il,:ilce,:adres,:telefon,
                    :email,:urun_gruplari,:notlar)""", d)
        conn.commit(); conn.close()
        self.yukle()

    def _duzenle(self):
        mid = self._get_secili_id()
        if not mid: return
        conn = get_conn()
        kayit = dict(conn.execute(
            "SELECT * FROM musteri WHERE id=?", (mid,)).fetchone())
        conn.close()
        dlg = MusteriDialog(self, kayit=kayit)
        if dlg.exec() != QDialog.DialogCode.Accepted: return
        d = dlg.get_veri()
        conn = get_conn()
        conn.execute("""UPDATE musteri SET
            dukkan_adi=:dukkan_adi, yetkili_adi=:yetkili_adi,
            il=:il, ilce=:ilce, adres=:adres, telefon=:telefon,
            email=:email, urun_gruplari=:urun_gruplari, notlar=:notlar
            WHERE id=:id""", {**d, "id": mid})
        conn.commit(); conn.close()
        self.yukle()

    def _sil(self):
        mid = self._get_secili_id()
        if not mid: return
        isim = self.tablo.item(
            self.tablo.selectionModel().selectedRows()[0].row(), 1).text()
        cevap = QMessageBox.question(
            self, "Sil", f"'{isim}' kalıcı olarak silinecek. Emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if cevap != QMessageBox.StandardButton.Yes: return
        conn = get_conn()
        conn.execute("DELETE FROM musteri WHERE id=?", (mid,))
        conn.commit(); conn.close()
        self.yukle()

    def _borc_isle(self):
        mid = self._get_secili_id()
        if not mid:
            QMessageBox.information(self, "Bilgi", "Önce müşteri seçin."); return
        conn = get_conn()
        kayit = dict(conn.execute(
            "SELECT * FROM musteri WHERE id=?", (mid,)).fetchone())
        conn.close()
        dlg = BorcDialog(self, kayit["dukkan_adi"], kayit["borc"])
        if dlg.exec() != QDialog.DialogCode.Accepted: return
        tip, tutar, delta, not_ = dlg.get_veri()
        conn = get_conn()
        conn.execute(
            "UPDATE musteri SET borc = borc + ? WHERE id=?", (delta, mid))
        conn.commit(); conn.close()
        islem = "Borç eklendi" if tip == "BORC" else "Ödeme alındı"
        yeni  = kayit["borc"] + delta
        QMessageBox.information(self, "Tamam",
            f"✓ {islem}: ₺{tutar:,.2f}\nYeni borç: ₺{yeni:,.2f}")
        self.yukle()

    def guncelle(self):
        self.yukle()


# ══════════════════════════════════════════════════════════════════════════
#  ANA MÜŞTERİ SAYFASI
# ══════════════════════════════════════════════════════════════════════════
class MusteriSayfasi(QWidget):

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.liste = MusteriListesiSayfasi()
        lay.addWidget(self.liste)

    def guncelle(self):
        self.liste.guncelle()
