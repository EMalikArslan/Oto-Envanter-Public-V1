"""
modules/genel.py
────────────────
Genel Durum — 3 sekme:

  1. İstatistik   — toplam stok, marka/kategori dağılımı, ciro özeti
  2. Eksik Liste  — kurallara göre az kalan ürünler
  3. Kural Yönet — hangi kategori/marka için eşik tanımlanacak
"""

import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta

from PyQt6.QtWidgets import (
    QListWidgetItem,
    QLineEdit,
    QListWidget,
    QCheckBox,
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QGridLayout,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFrame, QComboBox,
    QMessageBox, QDialog, QSpinBox, QScrollArea, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont

from core.database import get_conn
from core.tema import RENK
from core.widgets import StatKart, AyiriciCizgi, Badge


KAT_RENK = {
    "Beyin":   RENK["mavi"],
    "ABS":     RENK["yesil"],
    "Plastik": "#8E44AD",
}


# ══════════════════════════════════════════════════════════════════════════
#  Yardımcı: Mini bar bileşeni
# ══════════════════════════════════════════════════════════════════════════
class MiniBar(QFrame):
    """Yatay dolum çubuğu — marka dağılımı için."""
    def __init__(self, etiket, deger, maks, renk):
        super().__init__()
        self.setFixedHeight(36)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 4)
        lay.setSpacing(10)

        lbl = QLabel(str(etiket))
        lbl.setFixedWidth(160)
        lbl.setStyleSheet(
            f"font-size: 12px; font-weight: 600; color: {RENK['metin']}; "
            f"background: transparent;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(lbl)

        bar_bg = QFrame()
        bar_bg.setFixedHeight(14)
        bar_bg.setStyleSheet(
            f"background: {RENK['cizgi']}; border-radius: 7px;")
        bar_bg_lay = QHBoxLayout(bar_bg)
        bar_bg_lay.setContentsMargins(0, 0, 0, 0)
        bar_bg_lay.setSpacing(0)

        oran = (deger / maks) if maks else 0
        bar_ic = QFrame()
        bar_ic.setFixedHeight(14)
        bar_ic.setStyleSheet(
            f"background: {renk}; border-radius: 7px;")
        bar_ic.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        bar_ic.setFixedWidth(0)  # başlangıç — animate ile set edilir
        self._bar  = bar_ic
        self._oran = oran
        bar_bg_lay.addWidget(bar_ic)
        bar_bg_lay.addStretch()
        lay.addWidget(bar_bg, 1)

        lbl_val = QLabel(str(deger))
        lbl_val.setFixedWidth(45)
        lbl_val.setStyleSheet(
            f"font-size: 12px; font-weight: 700; color: {renk}; "
            f"background: transparent;")
        lay.addWidget(lbl_val)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        # Bar genişliği parent'a göre hesapla
        toplam_w = self.width() - 160 - 45 - 20
        self._bar.setFixedWidth(max(4, int(toplam_w * self._oran)))


# ══════════════════════════════════════════════════════════════════════════
#  1. İSTATİSTİK PANELİ
# ══════════════════════════════════════════════════════════════════════════
class IstatistikSayfasi(QWidget):

    def __init__(self):
        super().__init__()
        self._build()
        self.yukle()

    def _build(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        ic = QWidget()
        self._lay = QVBoxLayout(ic)
        self._lay.setContentsMargins(24, 20, 24, 20)
        self._lay.setSpacing(20)
        scroll.setWidget(ic)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        # ── Üst stat kartları ────────────────────────────────────────────
        self.s_toplam  = StatKart("Toplam Ürün Kalemi", "—", RENK["metin2"])
        self.s_stokta  = StatKart("Stokta Var",         "—", RENK["yesil"])
        self.s_sifir   = StatKart("Stoku Biten",        "—", RENK["aksan"])
        self.s_etiket  = StatKart("Etiket Bekliyor",    "—", RENK["sari"])

        kart_lay = QHBoxLayout()
        kart_lay.setSpacing(12)
        for s in [self.s_toplam, self.s_stokta, self.s_sifir, self.s_etiket]:
            kart_lay.addWidget(s)
        self._lay.addLayout(kart_lay)

        # ── Günlük ciro kartları ─────────────────────────────────────────
        ciro_lay = QHBoxLayout()
        ciro_lay.setSpacing(12)
        self.s_ciro_bugun  = StatKart("Bugünkü Ciro",    "₺—", RENK["mavi"])
        self.s_ciro_hafta  = StatKart("Bu Hafta Ciro",   "₺—", RENK["mavi"])
        self.s_satis_bugun = StatKart("Bugün Satış Adedi","—", RENK["metin2"])
        self.s_giris_bugun = StatKart("Bugün Mal Girişi", "—", RENK["yesil"])
        for s in [self.s_ciro_bugun, self.s_ciro_hafta,
                  self.s_satis_bugun, self.s_giris_bugun]:
            ciro_lay.addWidget(s)
        self._lay.addLayout(ciro_lay)
        self._lay.addWidget(AyiriciCizgi())

        # ── Kategori dağılımı ────────────────────────────────────────────
        lbl_kat = QLabel("KATEGORİ DAĞILIMI")
        lbl_kat.setStyleSheet(
            f"font-size: 10px; font-weight: 700; letter-spacing: 2px; "
            f"color: {RENK['metin2']};")
        self._lay.addWidget(lbl_kat)

        self.kat_grid = QGridLayout()
        self.kat_grid.setSpacing(12)
        self._lay.addLayout(self.kat_grid)
        self._lay.addWidget(AyiriciCizgi())

        # ── Marka/Kategori detay tablosu ─────────────────────────────────
        lbl_marka = QLabel("MARKA × KATEGORİ DETAY")
        lbl_marka.setStyleSheet(
            f"font-size: 10px; font-weight: 700; letter-spacing: 2px; "
            f"color: {RENK['metin2']};")
        self._lay.addWidget(lbl_marka)

        self.detay_tablo = QTableWidget()
        self.detay_tablo.setColumnCount(5)
        self.detay_tablo.setHorizontalHeaderLabels(
            ["MARKA", "KATEGORİ", "STOK KALEMI", "STOKTA VAR", "STOK SIFIR"])
        self.detay_tablo.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.detay_tablo.verticalHeader().setVisible(False)
        self.detay_tablo.setAlternatingRowColors(True)
        self.detay_tablo.setMaximumHeight(340)
        hh = self.detay_tablo.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.detay_tablo.verticalHeader().setDefaultSectionSize(32)
        self._lay.addWidget(self.detay_tablo)

        # ── Marka bar listesi ─────────────────────────────────────────────
        lbl_bar = QLabel("MARKA BAZLI STOK DAĞILIMI")
        lbl_bar.setStyleSheet(
            f"font-size: 10px; font-weight: 700; letter-spacing: 2px; "
            f"color: {RENK['metin2']};")
        self._lay.addWidget(lbl_bar)

        self.bar_container = QVBoxLayout()
        self.bar_container.setSpacing(4)
        self._lay.addLayout(self.bar_container)
        self._lay.addStretch()

    def yukle(self):
        conn = get_conn()
        df = pd.read_sql_query("SELECT * FROM stok", conn)

        # Hareket özeti
        bugun = date.today().isoformat()
        hafta_bas = (date.today() - timedelta(days=7)).isoformat()
        ozet = conn.execute("""
            SELECT hareket_tipi, COUNT(*) n, COALESCE(SUM(toplam_tutar),0) ciro
            FROM hareket WHERE date(zaman) >= ?
            GROUP BY hareket_tipi
        """, (hafta_bas,)).fetchall()
        bugun_ozet = conn.execute("""
            SELECT hareket_tipi, COUNT(*) n, COALESCE(SUM(toplam_tutar),0) ciro
            FROM hareket WHERE date(zaman) = ?
            GROUP BY hareket_tipi
        """, (bugun,)).fetchall()
        conn.close()

        # ── Üst kartlar ─────────────────────────────────────────────────
        tot = len(df)
        stk = (df["stok_miktari"] > 0).sum() if tot else 0
        sif = (df["stok_miktari"] <= 0).sum() if tot else 0
        etk = (df["etiket_basildi"] == "HAYIR").sum() if tot else 0
        self.s_toplam.set_deger(tot)
        self.s_stokta.set_deger(stk)
        self.s_sifir.set_deger(sif)
        self.s_etiket.set_deger(etk)

        def _ozet_bul(rows, tip, alan):
            for r in rows:
                if r["hareket_tipi"] == tip:
                    return r[alan]
            return 0

        ciro_b = _ozet_bul(bugun_ozet, "SATIS", "ciro")
        ciro_h = _ozet_bul(ozet, "SATIS", "ciro")
        sat_b  = _ozet_bul(bugun_ozet, "SATIS", "n")
        gir_b  = _ozet_bul(bugun_ozet, "MAL_GIRIS", "n")
        self.s_ciro_bugun.set_deger(f"₺{ciro_b:,.0f}")
        self.s_ciro_hafta.set_deger(f"₺{ciro_h:,.0f}")
        self.s_satis_bugun.set_deger(sat_b)
        self.s_giris_bugun.set_deger(gir_b)

        # ── Kategori kartları ────────────────────────────────────────────
        while self.kat_grid.count():
            w = self.kat_grid.takeAt(0).widget()
            if w: w.deleteLater()

        kategoriler = ["Beyin", "ABS", "Plastik"]
        for col, kat in enumerate(kategoriler):
            d = df[df["kategori"] == kat] if not df.empty else pd.DataFrame()
            n_toplam  = len(d)
            n_stokta  = (d["stok_miktari"] > 0).sum() if n_toplam else 0
            n_sifir   = n_toplam - n_stokta
            renk = KAT_RENK.get(kat, RENK["metin2"])

            kart = QFrame()
            kart.setObjectName("Kart")
            kart.setStyleSheet(
                f"QFrame#Kart {{ background: {RENK['yuzey']}; border-radius: 10px; "
                f"border: 1px solid {RENK['cizgi']}; border-top: 4px solid {renk}; }}")
            klay = QVBoxLayout(kart)
            klay.setContentsMargins(16, 14, 16, 14)
            klay.setSpacing(6)

            lbl_kat_adi = QLabel(kat.upper())
            lbl_kat_adi.setStyleSheet(
                f"font-size: 11px; font-weight: 700; letter-spacing: 1.5px; color: {renk};")
            lbl_n = QLabel(str(n_toplam))
            lbl_n.setStyleSheet(
                f"font-size: 32px; font-weight: 700; color: {RENK['metin']};")

            alt_lay = QHBoxLayout()
            alt_lay.setSpacing(12)
            lbl_var = QLabel(f"✓ {n_stokta} stokta")
            lbl_var.setStyleSheet(f"font-size: 11px; color: {RENK['yesil']};")
            lbl_bit = QLabel(f"✗ {n_sifir} bitti")
            lbl_bit.setStyleSheet(f"font-size: 11px; color: {RENK['aksan']};")
            alt_lay.addWidget(lbl_var)
            alt_lay.addWidget(lbl_bit)
            alt_lay.addStretch()

            klay.addWidget(lbl_kat_adi)
            klay.addWidget(lbl_n)
            klay.addLayout(alt_lay)
            self.kat_grid.addWidget(kart, 0, col)

        # ── Detay tablo ──────────────────────────────────────────────────
        if not df.empty:
            grp = df.groupby(["marka", "kategori"]).agg(
                kalem   = ("id",            "count"),
                stokta  = ("stok_miktari",  lambda x: (x > 0).sum()),
                sifir   = ("stok_miktari",  lambda x: (x <= 0).sum()),
            ).reset_index().sort_values(["marka", "kategori"])
        else:
            grp = pd.DataFrame(columns=["marka","kategori","kalem","stokta","sifir"])

        self.detay_tablo.setRowCount(len(grp))
        for i, (_, r) in enumerate(grp.iterrows()):
            vals = [r["marka"], r["kategori"],
                    str(r["kalem"]), str(r["stokta"]), str(r["sifir"])]
            kat_renk = KAT_RENK.get(r["kategori"], RENK["metin"])
            for j, val in enumerate(vals):
                item = QTableWidgetItem(val)
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                if j == 1:
                    item.setForeground(QColor(kat_renk))
                    item.setFont(QFont("", -1, QFont.Weight.Bold))
                if j == 4 and r["sifir"] > 0:
                    item.setForeground(QColor(RENK["aksan"]))
                self.detay_tablo.setItem(i, j, item)

        # ── Marka bar listesi ─────────────────────────────────────────────
        while self.bar_container.count():
            item = self.bar_container.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        if not df.empty:
            marka_stok = df.groupby("marka")["stok_miktari"].sum().sort_values(ascending=False)
            maks = marka_stok.max() if len(marka_stok) else 1
            for marka, adet in marka_stok.items():
                bar = MiniBar(marka, int(adet), int(maks), RENK["mavi"])
                self.bar_container.addWidget(bar)

    def guncelle(self):
        self.yukle()


# ══════════════════════════════════════════════════════════════════════════
#  2. EKSİK LİSTESİ
# ══════════════════════════════════════════════════════════════════════════
class EksikListesiSayfasi(QWidget):

    def __init__(self):
        super().__init__()
        self._build()
        self.yukle()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)

        ust = QHBoxLayout()
        lbl = QLabel("EKSİK / AZ KALAN ÜRÜNLER")
        lbl.setStyleSheet(
            f"font-size: 10px; font-weight: 700; letter-spacing: 2px; "
            f"color: {RENK['metin2']};")
        btn_yenile = QPushButton("Yenile")
        btn_yenile.setObjectName("BtnIkincil")
        btn_yenile.setFixedWidth(100)
        btn_yenile.clicked.connect(self.yukle)
        ust.addWidget(lbl)
        ust.addStretch()
        ust.addWidget(btn_yenile)
        lay.addLayout(ust)

        aciklama = QLabel(
            "Kural Yöneticisi'nde tanımlanan minimum stok eşiklerinin altına "
            "düşen ürünler burada listelenir.")
        aciklama.setWordWrap(True)
        aciklama.setStyleSheet(f"font-size: 12px; color: {RENK['metin2']};")
        lay.addWidget(aciklama)

        # Filtreler
        fil = QHBoxLayout()
        self.cb_kat = QComboBox()
        self.cb_kat.setMinimumHeight(36)
        self.cb_kat.addItems(["Tüm Kategoriler", "Beyin", "ABS", "Plastik"])
        self.cb_kat.currentIndexChanged.connect(self._filtrele)
        fil.addWidget(QLabel("Kategori:"))
        fil.addWidget(self.cb_kat)
        fil.addStretch()
        lay.addLayout(fil)

        self.tablo = QTableWidget()
        self.tablo.setColumnCount(6)
        self.tablo.setHorizontalHeaderLabels([
            "KATEGORİ", "MARKA", "MEVCUT STOK", "MİN EŞİK", "AÇIK", "DURUM"
        ])
        self.tablo.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tablo.setAlternatingRowColors(True)
        self.tablo.verticalHeader().setVisible(False)
        hh = self.tablo.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.tablo.verticalHeader().setDefaultSectionSize(34)
        lay.addWidget(self.tablo, 1)

        self.lbl_ozet = QLabel("")
        self.lbl_ozet.setStyleSheet(f"color: {RENK['metin2']}; font-size: 12px;")
        lay.addWidget(self.lbl_ozet)

    def yukle(self):
        conn = get_conn()
        kurallar = conn.execute("SELECT * FROM eksik_kural WHERE aktif=1").fetchall()
        self._rows = []
        for k in kurallar:
            kat=k["kategori"]; marka_raw=k["marka"]; esik=k["min_adet"]
            if "|" in marka_raw:
                marka,sid_str=marka_raw.split("|",1)
                try:
                    sid=int(sid_str)
                    row=conn.execute("SELECT yaygin_ad FROM stok WHERE id=?",(sid,)).fetchone()
                    urun=row["yaygin_ad"] if row else f"ID:{sid}"
                    mevcut=conn.execute("SELECT COUNT(*) FROM stok_birimi WHERE stok_id=? AND durum='DEPODA'",(sid,)).fetchone()[0]
                    gosterim=f"{marka} / {urun}"
                except: mevcut=0; gosterim=marka_raw
            else:
                marka=marka_raw; gosterim=marka
                mevcut=conn.execute("SELECT COUNT(*) FROM stok_birimi sb JOIN stok s ON s.id=sb.stok_id WHERE s.kategori=? AND s.marka=? AND sb.durum='DEPODA'",(kat,marka)).fetchone()[0]
            if mevcut < esik:
                self._rows.append({"kategori":kat,"marka":gosterim,"mevcut":mevcut,"esik":esik,"acik":max(0,esik-mevcut)})
        conn.close()
        self._filtrele()

    def _filtrele(self):
        kat = self.cb_kat.currentText()
        rows = self._rows
        if kat != "Tüm Kategoriler":
            rows = [r for r in rows if r["kategori"] == kat]

        # Kritikliğe göre sırala: en az stok önce
        rows.sort(key=lambda r: r["mevcut"])

        self.tablo.setRowCount(len(rows))
        for i, r in enumerate(rows):
            doluluk = r["mevcut"] / r["esik"] if r["esik"] else 1
            if doluluk == 0:
                durum = "KRİTİK"; durum_renk = RENK["aksan"]
                satir_renk = "#FFF0EF"
            elif doluluk < 0.5:
                durum = "DÜŞÜK"; durum_renk = RENK["sari"]
                satir_renk = "#FFFDF0"
            else:
                durum = "AZALDI"; durum_renk = RENK["mavi"]
                satir_renk = RENK["mavi_bg"]

            kat_renk = KAT_RENK.get(r["kategori"], RENK["metin"])
            vals = [r["kategori"], r["marka"], str(r["mevcut"]),
                    str(r["esik"]), str(r["acik"]), durum]

            for j, val in enumerate(vals):
                item = QTableWidgetItem(val)
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                item.setBackground(QColor(satir_renk))
                if j == 0:
                    item.setForeground(QColor(kat_renk))
                    item.setFont(QFont("", -1, QFont.Weight.Bold))
                if j == 5:
                    item.setForeground(QColor(durum_renk))
                    item.setFont(QFont("", -1, QFont.Weight.Bold))
                if j == 4 and r["acik"] > 0:
                    item.setForeground(QColor(RENK["aksan"]))
                    item.setFont(QFont("", -1, QFont.Weight.Bold))
                self.tablo.setItem(i, j, item)

        kritik = sum(1 for r in rows if r["mevcut"] == 0)
        self.lbl_ozet.setText(
            f"{len(rows)} eksik kalem  —  {kritik} kritik (stok sıfır)")

    def guncelle(self):
        self.yukle()


# ══════════════════════════════════════════════════════════════════════════
#  Kural Ekle Dialog
# ══════════════════════════════════════════════════════════════════════════
class KuralDialog(QDialog):
    def __init__(self, parent=None, mevcut=None):
        super().__init__(parent)
        self.setWindowTitle("Eksik Kuralı"); self.setMinimumSize(460,520)
        self.setStyleSheet(f"background-color:{RENK['yuzey']}; color:{RENK['metin']};")
        lay = QVBoxLayout(self); lay.setSpacing(10); lay.setContentsMargins(24,20,24,20)
        lbl=QLabel("Eksik Kuralı Tanımla"); lbl.setStyleSheet("font-size:16px;font-weight:700;")
        lay.addWidget(lbl); lay.addWidget(AyiriciCizgi())

        def satir(et,w):
            row=QHBoxLayout(); l=QLabel(et); l.setFixedWidth(130)
            l.setStyleSheet(f"font-size:12px;font-weight:600;color:{RENK['metin2']};")
            row.addWidget(l); row.addWidget(w); lay.addLayout(row); return w

        self.cb_kat=QComboBox(); self.cb_kat.setMinimumHeight(36)
        self.cb_kat.addItems(["Beyin","ABS","Plastik"])
        self.cb_kat.currentIndexChanged.connect(self._kat_degisti)
        satir("Urun Grubu:", self.cb_kat)

        self.cb_marka=QComboBox(); self.cb_marka.setMinimumHeight(36)
        self.cb_marka.currentIndexChanged.connect(self._marka_degisti)
        satir("Marka:", self.cb_marka)

        lbl2=QLabel("Urun Secimi:")
        lbl2.setStyleSheet(f"font-size:12px;font-weight:600;color:{RENK['metin2']};")
        lay.addWidget(lbl2)

        self.chk_tum=QCheckBox("Tum urunler (bu marka+grup icin)")
        self.chk_tum.setChecked(True)
        self.chk_tum.setStyleSheet(f"font-size:13px;font-weight:600;color:{RENK['metin']};")
        self.chk_tum.stateChanged.connect(lambda s: self.lst_urun.setEnabled(not bool(s)))
        lay.addWidget(self.chk_tum)

        self.lst_urun=QListWidget(); self.lst_urun.setMinimumHeight(150); self.lst_urun.setEnabled(False)
        self.lst_urun.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.lst_urun.setStyleSheet(f"QListWidget{{border:1.5px solid {RENK['cizgi']};border-radius:6px;background:{RENK['yuzey']};font-size:13px;}}QListWidget::item:selected{{background:{RENK['aksan_bg']};color:{RENK['metin']};}}")
        lay.addWidget(self.lst_urun)

        self.sb_esik=QSpinBox(); self.sb_esik.setRange(1,9999); self.sb_esik.setValue(3); self.sb_esik.setMinimumHeight(36)
        satir("Min. Stok Adedi:", self.sb_esik)

        self._kat_degisti()

        if mevcut:
            self.cb_kat.setCurrentText(mevcut.get("kategori","Beyin"))
            marka_raw=mevcut.get("marka","*")
            if "|" in marka_raw:
                marka,sid_str=marka_raw.split("|",1)
                self.cb_marka.setCurrentText(marka); self._marka_degisti()
                self.chk_tum.setChecked(False)
                for i in range(self.lst_urun.count()):
                    if str(self.lst_urun.item(i).data(Qt.ItemDataRole.UserRole))==sid_str:
                        self.lst_urun.item(i).setSelected(True); break
            else:
                if marka_raw!="*": self.cb_marka.setCurrentText(marka_raw)
                self.chk_tum.setChecked(True)
            self.sb_esik.setValue(mevcut.get("min_adet",3))

        lay.addWidget(AyiriciCizgi())
        btn_lay=QHBoxLayout()
        bi=QPushButton("Iptal"); bi.setObjectName("BtnIkincil"); bi.clicked.connect(self.reject)
        bk=QPushButton("Kaydet"); bk.setObjectName("BtnAksan"); bk.clicked.connect(self._kaydet)
        btn_lay.addWidget(bi); btn_lay.addWidget(bk); lay.addLayout(btn_lay)

    def _kat_degisti(self):
        kat=self.cb_kat.currentText()
        conn=get_conn()
        rows=conn.execute("SELECT DISTINCT marka FROM stok WHERE kategori=? AND marka!='-' ORDER BY marka",(kat,)).fetchall()
        conn.close()
        self.cb_marka.blockSignals(True); self.cb_marka.clear()
        self.cb_marka.addItems([r[0] for r in rows]); self.cb_marka.blockSignals(False)
        self._marka_degisti()

    def _marka_degisti(self):
        kat=self.cb_kat.currentText(); marka=self.cb_marka.currentText()
        conn=get_conn()
        rows=conn.execute("""SELECT s.id,s.yaygin_ad,COALESCE(d.n,0) dep
               FROM stok s LEFT JOIN (SELECT stok_id,COUNT(*) n FROM stok_birimi WHERE durum='DEPODA' GROUP BY stok_id) d ON d.stok_id=s.id
               WHERE s.kategori=? AND s.marka=? ORDER BY s.yaygin_ad""",(kat,marka)).fetchall()
        conn.close(); self.lst_urun.clear()
        for r in rows:
            item=QListWidgetItem(f"{r['yaygin_ad']}  ({r['dep']} depoda)  [ID:{r['id']}]")
            item.setData(Qt.ItemDataRole.UserRole,r["id"]); self.lst_urun.addItem(item)

    def _kaydet(self):
        if not self.chk_tum.isChecked() and not self.lst_urun.selectedItems():
            QMessageBox.warning(self,"Uyari","Urun secin veya 'Tum urunler' isaretleyin."); return
        self.accept()

    def get_veri(self):
        kat=self.cb_kat.currentText(); marka=self.cb_marka.currentText(); esik=self.sb_esik.value()
        if self.chk_tum.isChecked():
            return [{"kategori":kat,"marka":marka,"min_adet":esik}]
        return [{"kategori":kat,"marka":f"{marka}|{item.data(Qt.ItemDataRole.UserRole)}","min_adet":esik}
                for item in self.lst_urun.selectedItems()]


class KuralYoneticisiSayfasi(QWidget):

    def __init__(self):
        super().__init__()
        self._build()
        self.yukle()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)

        ust = QHBoxLayout()
        lbl = QLabel("EKSİK KURAL YÖNETİCİSİ")
        lbl.setStyleSheet(
            f"font-size: 10px; font-weight: 700; letter-spacing: 2px; "
            f"color: {RENK['metin2']};")
        btn_ekle = QPushButton("+ Kural Ekle")
        btn_ekle.setObjectName("BtnAksan")
        btn_ekle.clicked.connect(self._kural_ekle)
        btn_sil = QPushButton("Sil")
        btn_sil.setObjectName("BtnTehlike")
        btn_sil.clicked.connect(self._kural_sil)
        ust.addWidget(lbl); ust.addStretch()
        ust.addWidget(btn_sil); ust.addWidget(btn_ekle)
        lay.addLayout(ust)

        aciklama = QLabel(
            "Bir kategori + marka kombinasyonu için minimum stok eşiği tanımlayın.\n"
            "Stok bu eşiğin altına düşünce Eksik Listesi'nde görünür.")
        aciklama.setWordWrap(True)
        aciklama.setStyleSheet(f"font-size: 12px; color: {RENK['metin2']};")
        lay.addWidget(aciklama)

        self.tablo = QTableWidget()
        self.tablo.setColumnCount(4)
        self.tablo.setHorizontalHeaderLabels(
            ["KATEGORİ", "MARKA", "MİN EŞİK", "AKTİF"])
        self.tablo.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tablo.setAlternatingRowColors(True)
        self.tablo.verticalHeader().setVisible(False)
        self.tablo.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tablo.doubleClicked.connect(self._kural_duzenle)
        hh = self.tablo.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.tablo.verticalHeader().setDefaultSectionSize(34)
        lay.addWidget(self.tablo, 1)

        lbl2 = QLabel("İpucu: Çift tıklayarak kuralı düzenleyebilirsiniz.")
        lbl2.setStyleSheet(f"font-size: 11px; color: {RENK['metin3']};")
        lay.addWidget(lbl2)

    def yukle(self):
        conn = get_conn()
        rows = conn.execute(
            "SELECT * FROM eksik_kural ORDER BY kategori, marka").fetchall()
        conn.close()
        self._rows = [dict(r) for r in rows]

        kat_renk = KAT_RENK
        self.tablo.setRowCount(len(self._rows))
        for i, r in enumerate(self._rows):
            vals = [r["kategori"], r["marka"],
                    str(r["min_adet"]), "✓ Aktif" if r["aktif"] else "— Pasif"]
            renk = kat_renk.get(r["kategori"], RENK["metin"])
            for j, val in enumerate(vals):
                item = QTableWidgetItem(val)
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                if j == 0:
                    item.setForeground(QColor(renk))
                    item.setFont(QFont("", -1, QFont.Weight.Bold))
                if j == 3:
                    item.setForeground(QColor(
                        RENK["yesil"] if r["aktif"] else RENK["metin3"]))
                self.tablo.setItem(i, j, item)

    def _kural_ekle(self):
        dlg = KuralDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted: return
        d = dlg.get_veri()
        conn = get_conn()
        # Aynı kombinasyon varsa güncelle
        mevcut = conn.execute(
            "SELECT id FROM eksik_kural WHERE kategori=? AND marka=?",
            (d["kategori"], d["marka"])).fetchone()
        if mevcut:
            conn.execute(
                "UPDATE eksik_kural SET min_adet=?, aktif=1 WHERE id=?",
                (d["min_adet"], mevcut["id"]))
        else:
            conn.execute(
                "INSERT INTO eksik_kural (kategori,marka,min_adet) VALUES (?,?,?)",
                (d["kategori"], d["marka"], d["min_adet"]))
        conn.commit(); conn.close()
        self.yukle()

    def _kural_duzenle(self):
        rows = self.tablo.selectionModel().selectedRows()
        if not rows: return
        r = self._rows[rows[0].row()]
        dlg = KuralDialog(self, mevcut=r)
        if dlg.exec() != QDialog.DialogCode.Accepted: return
        d = dlg.get_veri()
        conn = get_conn()
        conn.execute(
            "UPDATE eksik_kural SET kategori=?, marka=?, min_adet=? WHERE id=?",
            (d["kategori"], d["marka"], d["min_adet"], r["id"]))
        conn.commit(); conn.close()
        self.yukle()

    def _kural_sil(self):
        rows = self.tablo.selectionModel().selectedRows()
        if not rows: return
        r = self._rows[rows[0].row()]
        cevap = QMessageBox.question(
            self, "Sil",
            f"{r['kategori']} / {r['marka']} kuralı silinecek. Emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if cevap != QMessageBox.StandardButton.Yes: return
        conn = get_conn()
        conn.execute("DELETE FROM eksik_kural WHERE id=?", (r["id"],))
        conn.commit(); conn.close()
        self.yukle()

    def guncelle(self):
        self.yukle()


# ══════════════════════════════════════════════════════════════════════════
#  ANA GENEL DURUM SAYFASI
# ══════════════════════════════════════════════════════════════════════════
class GenelSayfasi(QWidget):

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        self.istat_s  = IstatistikSayfasi()
        self.eksik_s  = EksikListesiSayfasi()
        self.kural_s  = KuralYoneticisiSayfasi()

        self.tabs.addTab(self.istat_s,  "  📊  İstatistik  ")
        self.tabs.addTab(self.eksik_s,  "  ⚠  Eksik Liste  ")
        self.tabs.addTab(self.kural_s,  "  ⚙  Kural Yöneticisi  ")
        self.tabs.currentChanged.connect(self._sekme_degisti)
        lay.addWidget(self.tabs, 1)

    def _sekme_degisti(self, idx):
        if idx == 0: self.istat_s.guncelle()
        elif idx == 1: self.eksik_s.guncelle()
        elif idx == 2: self.kural_s.guncelle()

    def guncelle(self):
        self._sekme_degisti(self.tabs.currentIndex())
