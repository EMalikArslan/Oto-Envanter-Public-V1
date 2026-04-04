import os
import pandas as pd
from PyQt6.QtWidgets import (
    QMenu,
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLineEdit, QComboBox, QLabel, QFileDialog, QMessageBox,
    QDialog, QCheckBox, QFrame, QHeaderView, QAbstractItemView,
    QSpinBox, QProgressDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QFont

from core.database import get_conn, v, to_int, birim_ekle, stok_miktari_guncelle
from core.tema import RENK
from core.widgets import StatKart, AyiriciCizgi
from core.etiket import etiket_olustur, yazici_gonder, yazici_listesi
from core.sheets import get_sheets

KATEGORILER = ["Beyin", "ABS", "Plastik"]

class _NumericItem(QTableWidgetItem):
    def __lt__(self, other):
        try:    return int(self.text()) < int(other.text())
        except: return self.text() < other.text()


# ── Import Thread ──────────────────────────────────────────────────────────
class ImportThread(QThread):
    ilerleme = pyqtSignal(int, int)
    bitti    = pyqtSignal(int, int)
    hata     = pyqtSignal(str)

    def __init__(self, dosyalar, kategori):
        super().__init__()
        self.dosyalar = dosyalar
        self.kategori = kategori

    def run(self):
        try:
            conn = get_conn()
            eklenen = atlanan = 0
            for dosya in self.dosyalar:
                try:
                    df = pd.read_csv(dosya, encoding="utf-8-sig")
                except:
                    try: df = pd.read_csv(dosya, encoding="latin-1")
                    except Exception as e:
                        self.hata.emit(str(e)); continue

                for i, row in df.iterrows():
                    self.ilerleme.emit(i + 1, len(df))
                    try:
                        refs = [v(row.get("Marka Ref No", "-")),
                                v(row.get("Ref No", "-")),
                                v(row.get("Ref No.1", "-")),
                                v(row.get("Ref No.2", "-")),
                                v(row.get("Ref No.3", "-"))]
                        adet = to_int(row.get("Stok Durumu", 1)) or 1
                        cursor = conn.execute(
                            """INSERT INTO stok
                               (kategori,marka,yaygin_ad,motor,
                                ref1,ref2,ref3,ref4,ref5,fiyat,stok_miktari)
                               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                            (self.kategori,
                             v(row.get("Ürün Grubu/Marka")),
                             v(row.get("Yaygın Ad")),
                             v(row.get("Motor Bilgisi")),
                             refs[0],refs[1],refs[2],refs[3],refs[4],
                             v(row.get("Fiyat")), adet))
                        stok_id = cursor.lastrowid
                        conn.commit()
                        # Her adet için fiziksel birim oluştur
                        for s in range(1, adet + 1):
                            barkod = f"{stok_id}-{s}"
                            conn.execute(
                                "INSERT OR IGNORE INTO stok_birimi (stok_id, barkod_id) VALUES (?,?)",
                                (stok_id, barkod))
                        conn.commit()
                        eklenen += 1
                    except: atlanan += 1
            conn.close()
            self.bitti.emit(eklenen, atlanan)
        except Exception as e:
            self.hata.emit(str(e))


# ── Etiket Oluşturma Thread (UI donmasını önler) ──────────────────────────
class EtiketThread(QThread):
    bitti    = pyqtSignal(str, str)   # (barkod_id, dosya_yolu)
    hata     = pyqtSignal(str, str)   # (barkod_id, hata_mesaji)

    def __init__(self, barkod_id, stok_id, kategori, marka, ad, secili_refler):
        super().__init__()
        self.barkod_id     = barkod_id
        self.stok_id       = stok_id
        self.kategori      = kategori
        self.marka         = marka
        self.ad            = ad
        self.secili_refler = secili_refler

    def run(self):
        try:
            yol = etiket_olustur(self.barkod_id, self.stok_id,
                                  self.kategori, self.marka,
                                  self.ad, self.secili_refler)
            self.bitti.emit(self.barkod_id, yol)
        except Exception as e:
            self.hata.emit(self.barkod_id, str(e))


# ── Ref Seçim Dialog ──────────────────────────────────────────────────────

class StokYuklemeThread(QThread):
    bitti = pyqtSignal(object, int, int, int, list)
    def __init__(self, kategori):
        super().__init__(); self.kategori = kategori
    def run(self):
        try:
            import pandas as pd
            conn = get_conn()
            df = pd.read_sql_query("""
                SELECT s.*,
                    COALESCE(d.depoda,0) AS depoda_adet,
                    COALESCE(t.turda,0)  AS turda_adet,
                    COALESCE(e.bekl,0)   AS etiket_bekleyen
                FROM stok s
                LEFT JOIN (SELECT stok_id,COUNT(*) depoda FROM stok_birimi WHERE durum='DEPODA' GROUP BY stok_id) d ON d.stok_id=s.id
                LEFT JOIN (SELECT stok_id,COUNT(*) turda  FROM stok_birimi WHERE durum='TURDA'  GROUP BY stok_id) t ON t.stok_id=s.id
                LEFT JOIN (SELECT stok_id,COUNT(*) bekl   FROM stok_birimi WHERE durum='DEPODA' AND etiket_basildi='HAYIR' GROUP BY stok_id) e ON e.stok_id=s.id
                WHERE s.kategori=? ORDER BY CAST(s.id AS INTEGER) ASC
            """, conn, params=(self.kategori,))
            markalar = sorted([m for m in df["marka"].dropna().unique().tolist() if m and m!="-"]) if not df.empty else []
            conn.close()
            self.bitti.emit(df, int(df["depoda_adet"].sum()) if not df.empty else 0,
                           int(df["turda_adet"].sum()) if not df.empty else 0,
                           int(df["etiket_bekleyen"].sum()) if not df.empty else 0, markalar)
        except Exception as e:
            import pandas as pd
            self.bitti.emit(pd.DataFrame(),0,0,0,[])


class RefSecimDialog(QDialog):
    def __init__(self, refs, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Etiket — Referans Seçimi")
        self.setMinimumWidth(320)
        self.setStyleSheet(f"background:{RENK['yuzey']}; color:{RENK['metin']};")
        lay = QVBoxLayout(self)
        lay.setSpacing(10); lay.setContentsMargins(20,20,20,20)
        lay.addWidget(QLabel("Etikete basılacak referansları seçin:"))
        lay.addWidget(AyiriciCizgi())
        self.checks = []
        for ref in refs:
            if ref and ref != "-":
                cb = QCheckBox(str(ref)); cb.setChecked(True)
                cb.setStyleSheet(f"font-size:14px; font-weight:600; color:{RENK['metin']};")
                lay.addWidget(cb); self.checks.append(cb)
        lay.addWidget(AyiriciCizgi())
        btn_lay = QHBoxLayout()
        bi = QPushButton("İptal"); bi.setObjectName("BtnIkincil"); bi.clicked.connect(self.reject)
        bk = QPushButton("Etiket Oluştur"); bk.setObjectName("BtnAksan"); bk.clicked.connect(self.accept)
        btn_lay.addWidget(bi); btn_lay.addWidget(bk); lay.addLayout(btn_lay)
    def get_secili(self): return [c.text() for c in self.checks if c.isChecked()]


# ── Birim Yönetim Dialog (bir ürünün parçalarını göster) ──────────────────
class BirimDialog(QDialog):
    def __init__(self, stok_id, marka, ad, parent=None):
        super().__init__(parent)
        self.stok_id = stok_id
        self.setWindowTitle(f"Birimler — {marka} / {ad}")
        self.setMinimumSize(500, 400)
        self.setStyleSheet(f"background:{RENK['yuzey']}; color:{RENK['metin']};")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20,20,20,20); lay.setSpacing(12)

        lbl = QLabel(f"{marka}  /  {ad}  —  Fiziksel Birimler")
        lbl.setStyleSheet("font-size:15px; font-weight:700;")
        lay.addWidget(lbl)
        lay.addWidget(AyiriciCizgi())

        self.tablo = QTableWidget()
        self.tablo.setColumnCount(4)
        self.tablo.setHorizontalHeaderLabels(["BARKOD ID", "DURUM", "GİRİŞ TARİHİ", "ETİKET"])
        self.tablo.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tablo.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tablo.verticalHeader().setVisible(False)
        self.tablo.setAlternatingRowColors(True)
        hh = self.tablo.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tablo.verticalHeader().setDefaultSectionSize(30)
        lay.addWidget(self.tablo, 1)

        alt = QHBoxLayout()
        btn_yenile = QPushButton("Yenile"); btn_yenile.setObjectName("BtnIkincil")
        btn_yenile.clicked.connect(self.yukle)
        btn_etiket = QPushButton("Seçileni Etiketle"); btn_etiket.setObjectName("BtnAksan")
        btn_etiket.clicked.connect(self.birim_etiketle)
        alt.addWidget(btn_yenile); alt.addStretch(); alt.addWidget(btn_etiket)
        lay.addLayout(alt)
        self.yukle()

    def yukle(self):
        conn = get_conn()
        rows = conn.execute(
            "SELECT * FROM stok_birimi WHERE stok_id=? ORDER BY id",
            (self.stok_id,)).fetchall()
        conn.close()
        durum_renk = {"DEPODA": RENK["yesil"], "TURDA": RENK["mavi"],
                      "SATILDI": RENK["metin3"], "KAYIP": RENK["aksan"]}
        self.tablo.setRowCount(len(rows))
        for i, r in enumerate(rows):
            vals = [r["barkod_id"], r["durum"],
                    str(r["giris_tarihi"] or "")[:16],
                    "✓" if r["etiket_basildi"] == "EVET" else "—"]
            for j, val in enumerate(vals):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                if j == 1:
                    item.setForeground(QColor(durum_renk.get(r["durum"], RENK["metin"])))
                    item.setFont(QFont("", -1, QFont.Weight.Bold))
                self.tablo.setItem(i, j, item)

    def birim_etiketle(self):
        rows = self.tablo.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(self, "Bilgi", "Önce bir birim seçin."); return
        barkod_id = self.tablo.item(rows[0].row(), 0).text()
        conn = get_conn()
        stok = conn.execute(
            "SELECT s.*, sb.id as birim_id FROM stok s "
            "JOIN stok_birimi sb ON sb.stok_id=s.id "
            "WHERE sb.barkod_id=?", (barkod_id,)).fetchone()
        conn.close()
        if not stok: return
        refs = [stok["ref1"], stok["ref2"], stok["ref3"],
                stok["ref4"], stok["ref5"]]
        refs = [r for r in refs if r and r != "-"]
        dlg = RefSecimDialog(refs, self)
        if dlg.exec() != QDialog.DialogCode.Accepted: return
        try:
            yol = etiket_olustur(barkod_id, stok["id"],
                                  stok["kategori"], stok["marka"],
                                  stok["yaygin_ad"], dlg.get_secili())
            conn = get_conn()
            conn.execute("UPDATE stok_birimi SET etiket_basildi='EVET' WHERE barkod_id=?",
                         (barkod_id,))
            conn.commit(); conn.close()
            yazicilar = yazici_listesi()
            ok, _ = yazici_gonder(yol, yazicilar[0] if yazicilar else None)
            if not ok:
                import subprocess as sp, sys
                if sys.platform == "win32": os.startfile(os.path.dirname(yol))
                else: sp.Popen(["xdg-open", os.path.dirname(yol)])
            self.yukle()
            QMessageBox.information(self, "OK", f"✓ Etiket: {barkod_id}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))


# ── Stok Ekle / Düzenle Dialog ────────────────────────────────────────────
class StokDialog(QDialog):
    def __init__(self, kategori, kayit=None, parent=None):
        super().__init__(parent)
        self.kayit = kayit
        self.setWindowTitle("Ürün Düzenle" if kayit else "Yeni Ürün Ekle")
        self.setMinimumWidth(520)
        self.setMinimumHeight(500)
        self.setStyleSheet(f"background:{RENK['yuzey']}; color:{RENK['metin']};")

        ana = QVBoxLayout(self)
        ana.setSpacing(10); ana.setContentsMargins(16, 16, 16, 16)

        if kayit:
            # Düzenleme: 2 sekme
            self.tabs = QTabWidget()
            self.tabs.setDocumentMode(True)

            # ── Sekme 1: Bilgi Düzenleme ──────────────────────────────────
            bilgi_w = QWidget()
            bilgi_lay = QVBoxLayout(bilgi_w)
            bilgi_lay.setContentsMargins(16, 16, 16, 8)
            self._bilgi_form(bilgi_lay, kayit, kategori)

            # ── Sekme 2: Stok Yönetimi ────────────────────────────────────
            stok_w = QWidget()
            stok_lay = QVBoxLayout(stok_w)
            stok_lay.setContentsMargins(16, 16, 16, 8)
            self._stok_form(stok_lay, kayit)

            self.tabs.addTab(bilgi_w, "  📝  Bilgi Düzenleme  ")
            self.tabs.addTab(stok_w,  "  📦  Stok Yönetimi  ")
            ana.addWidget(self.tabs, 1)
        else:
            # Yeni ürün: tek form
            self.tabs = None
            w = QWidget()
            lay = QVBoxLayout(w)
            lay.setContentsMargins(8, 8, 8, 8)
            self._bilgi_form(lay, None, kategori)
            lbl_adet = QLabel("Adet (fiziksel)")
            lbl_adet.setStyleSheet(f"font-size:12px; font-weight:600; color:{RENK['metin2']};")
            self.adet_sb = QSpinBox()
            self.adet_sb.setRange(1, 999); self.adet_sb.setValue(1)
            row = QHBoxLayout()
            l = QLabel("Adet (fiziksel)"); l.setFixedWidth(120)
            l.setStyleSheet(f"font-size:12px; font-weight:600; color:{RENK['metin2']};")
            row.addWidget(l); row.addWidget(self.adet_sb)
            lay.addLayout(row)
            ana.addWidget(w, 1)
            self.ekle_sb = None
            self.cikar_sb = None

        # ── Alt butonlar ──────────────────────────────────────────────────
        ana.addWidget(AyiriciCizgi())
        btn_lay = QHBoxLayout()
        bi = QPushButton("İptal"); bi.setObjectName("BtnIkincil"); bi.clicked.connect(self.reject)
        bk = QPushButton("Kaydet"); bk.setObjectName("BtnAksan"); bk.clicked.connect(self._kaydet)
        btn_lay.addWidget(bi); btn_lay.addWidget(bk)
        ana.addLayout(btn_lay)

    def _bilgi_form(self, lay, kayit, kategori):
        """Kategori, marka, referanslar, fiyat alanları."""
        def satir(et, w):
            row = QHBoxLayout()
            l = QLabel(et); l.setFixedWidth(120)
            l.setStyleSheet(f"font-size:12px; font-weight:600; color:{RENK['metin2']};")
            row.addWidget(l); row.addWidget(w); lay.addLayout(row); return w

        self.kat_cb = QComboBox(); self.kat_cb.addItems(KATEGORILER)
        self.kat_cb.setCurrentText(kayit["kategori"] if kayit else kategori)
        satir("Kategori", self.kat_cb)
        self.marka = satir("Marka",     QLineEdit(kayit["marka"] if kayit else ""))
        self.ad    = satir("Yaygın Ad", QLineEdit(kayit["yaygin_ad"] if kayit else ""))
        self.motor = satir("Motor",     QLineEdit(kayit["motor"] if kayit else ""))
        self.refs  = []
        for i in range(1, 6):
            val = "" if not kayit or kayit.get(f"ref{i}", "") in ("-", "") else kayit.get(f"ref{i}", "")
            self.refs.append(satir(f"Referans {i}", QLineEdit(val)))
        self.fiyat = satir("Fiyat",     QLineEdit(kayit["fiyat"] if kayit else ""))
        lay.addStretch()

    def _stok_form(self, lay, kayit):
        """Birim ekle / çıkar ve mevcut birimler."""
        def satir(et, w):
            row = QHBoxLayout()
            l = QLabel(et); l.setFixedWidth(130)
            l.setStyleSheet(f"font-size:12px; font-weight:600; color:{RENK['metin2']};")
            row.addWidget(l); row.addWidget(w); lay.addLayout(row); return w

        self.ekle_sb = satir("Birim Ekle (+)", QSpinBox())
        self.ekle_sb.setRange(0, 999); self.ekle_sb.setValue(0)
        self.ekle_sb.setToolTip("Depoya eklenecek yeni fiziksel birim sayısı")

        self.cikar_sb = satir("Birim Çıkar (−)", QSpinBox())
        self.cikar_sb.setRange(0, 999); self.cikar_sb.setValue(0)
        self.cikar_sb.setToolTip("Depodan çıkarılacak (SATILDI olarak işaretlenecek) birim sayısı")

        lay.addWidget(AyiriciCizgi())

        # Mevcut birimler tablosu
        lbl = QLabel("Mevcut Birimler")
        lbl.setStyleSheet(f"font-size:12px; font-weight:700; color:{RENK['metin2']};")
        lay.addWidget(lbl)

        from core.database import get_conn as _gc
        try:
            with _gc() as conn:
                birimler = conn.execute(
                    "SELECT barkod_id, durum FROM stok_birimi WHERE stok_id=? ORDER BY id",
                    (kayit["id"],)
                ).fetchall()
        except Exception:
            birimler = []

        birim_lay = QHBoxLayout()
        birim_lay.setSpacing(6)
        birim_lay.setAlignment(Qt.AlignmentFlag.AlignLeft)
        durum_renk = {"DEPODA": "#4ade80", "TURDA": "#60a5fa", "SATILDI": "#888888"}
        for b in birimler:
            renk = durum_renk.get(b[1] if isinstance(b, tuple) else b["durum"], "#888")
            lbl_b = QLabel(str(b[0] if isinstance(b, tuple) else b["barkod_id"]))
            lbl_b.setStyleSheet(
                f"background:{renk}22; color:{renk}; border:1px solid {renk}55;"
                f"border-radius:4px; padding:2px 6px; font-size:11px;"
            )
            birim_lay.addWidget(lbl_b)

        birim_w = QWidget()
        birim_w.setLayout(birim_lay)
        from PyQt6.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidget(birim_w)
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(100)
        scroll.setStyleSheet("QScrollArea{border:none;}")
        lay.addWidget(scroll)
        lay.addStretch()

        self.adet_sb = None

    def _kaydet(self):
        if not self.marka.text().strip():
            QMessageBox.warning(self, "Uyarı", "Marka boş olamaz!"); return
        self.accept()

    def get_veri(self):
        refs = [r.text().strip() or "-" for r in self.refs]
        return {
            "kategori":  self.kat_cb.currentText(),
            "marka":     self.marka.text().strip() or "-",
            "yaygin_ad": self.ad.text().strip() or "-",
            "motor":     self.motor.text().strip() or "-",
            "ref1": refs[0], "ref2": refs[1], "ref3": refs[2],
            "ref4": refs[3], "ref5": refs[4],
            "fiyat":     self.fiyat.text().strip() or "-",
            "adet":      self.adet_sb.value() if self.adet_sb else 1,
        }


# ── Ana Stok Sayfası ──────────────────────────────────────────────────────
class StokSayfasi(QWidget):
    def __init__(self):
        super().__init__()
        self.aktif_kat = KATEGORILER[0]
        self.df = pd.DataFrame()
        self._build_ui()
        self.yukle()
        # Otomatik Google Sheets sync — her 20 dakikada bir
        self._sync_timer = QTimer(self)
        self._sync_timer.timeout.connect(self._silent_sheets_sync)
        self._sync_timer.start(20 * 60 * 1000)

    def _build_ui(self):
        ana = QVBoxLayout(self)
        ana.setContentsMargins(24, 20, 24, 20); ana.setSpacing(16)

        # Kategori butonları
        kat_lay = QHBoxLayout(); kat_lay.setSpacing(8)
        self.kat_butonlar = {}
        for kat in KATEGORILER:
            btn = QPushButton(kat.upper()); btn.setCheckable(True); btn.setFixedHeight(36)
            btn.clicked.connect(lambda _, k=kat: self._kat_sec(k))
            btn.setStyleSheet(self._kat_btn_stil(False))
            self.kat_butonlar[kat] = btn; kat_lay.addWidget(btn)
        kat_lay.addStretch()
        btn_sablon = QPushButton("⬇  Şablon İndir")
        btn_sablon.setObjectName("BtnIkincil"); btn_sablon.setFixedHeight(36)
        btn_sablon.clicked.connect(self.sablon_indir)
        kat_lay.addWidget(btn_sablon); ana.addLayout(kat_lay)

        # Stat kartları
        stat_lay = QHBoxLayout(); stat_lay.setSpacing(12)
        self.s_toplam   = StatKart("Ürün Kalemi",     "0", RENK["metin2"])
        self.s_stok     = StatKart("Depoda",           "0", RENK["yesil"])
        self.s_turda    = StatKart("Turda",            "0", RENK["mavi"])
        self.s_bekliyor = StatKart("Etiket Bekliyor", "0", RENK["aksan"])
        for s in [self.s_toplam, self.s_stok, self.s_turda, self.s_bekliyor]:
            stat_lay.addWidget(s)
        ana.addLayout(stat_lay)

        # Filtreler
        fil_lay = QHBoxLayout(); fil_lay.setSpacing(10)
        self.ara_txt = QLineEdit(); self.ara_txt.setPlaceholderText("Ara — marka, model, referans...")
        self.ara_txt.setMinimumHeight(38); self.ara_txt.textChanged.connect(self._filtrele)
        self.cb_durum = QComboBox(); self.cb_durum.setMinimumHeight(38)
        self.cb_durum.addItems(["Tüm Durumlar", "Etiket Bekliyor", "Etiketli"])
        self.cb_durum.currentIndexChanged.connect(self._filtrele)
        self.cb_marka = QComboBox(); self.cb_marka.setMinimumHeight(38)
        self.cb_marka.addItem("Tüm Markalar")
        self.cb_marka.currentIndexChanged.connect(self._filtrele)
        fil_lay.addWidget(self.ara_txt, 3); fil_lay.addWidget(self.cb_durum, 1)
        fil_lay.addWidget(self.cb_marka, 1); ana.addLayout(fil_lay)

        # Tablo — ADET kolonu eklendi
        self.tablo = QTableWidget()
        self.tablo.setColumnCount(14)
        self.tablo.setHorizontalHeaderLabels([
            "ID", "KATEGORİ", "MARKA", "YAYGIN AD", "MOTOR",
            "REF 1", "REF 2", "REF 3", "REF 4", "REF 5",
            "FİYAT", "DEPODA", "TURDA", "ETİKET"
        ])
        self.tablo.setAlternatingRowColors(True)
        self.tablo.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tablo.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tablo.verticalHeader().setVisible(False)
        self.tablo.setSortingEnabled(True)
        hh = self.tablo.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(0,  QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1,  QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(11, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(12, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(13, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3,  QHeaderView.ResizeMode.Stretch)
        self.tablo.verticalHeader().setDefaultSectionSize(34)
        self.tablo.doubleClicked.connect(self._duzenle)
        self.tablo.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tablo.customContextMenuRequested.connect(self._sag_menu)
        ana.addWidget(self.tablo, 1)

        # Alt butonlar
        alt_lay = QHBoxLayout(); alt_lay.setSpacing(10)
        btn_yukle = QPushButton("⬆  CSV Yükle"); btn_yukle.setObjectName("BtnIkincil")
        btn_yukle.clicked.connect(self.import_csv)
        btn_ekle = QPushButton("+ Ürün Ekle"); btn_ekle.setObjectName("BtnIkincil")
        btn_ekle.clicked.connect(self.urun_ekle)
        btn_birim = QPushButton("📦  Birimleri Gör"); btn_birim.setObjectName("BtnIkincil")
        btn_birim.clicked.connect(self._birim_goster)
        btn_sil = QPushButton("Sil"); btn_sil.setObjectName("BtnTehlike")
        btn_sil.clicked.connect(self.secilenleri_sil)
        self.btn_etiket = QPushButton("🖨  Seçilenleri Etiketle"); self.btn_etiket.setObjectName("BtnAksan")
        self.btn_etiket.clicked.connect(self.etiketle)
        self.lbl_secim = QLabel(""); self.lbl_secim.setStyleSheet(f"color:{RENK['metin2']}; font-size:12px;")
        btn_duzenle = QPushButton('Duzenle'); btn_duzenle.setObjectName('BtnIkincil')
        btn_duzenle.clicked.connect(self._duzenle)
        btn_sheets = QPushButton('Sheets Gonder'); btn_sheets.setObjectName('BtnIkincil')
        btn_sheets.clicked.connect(self.stok_sheets_gonder)
        alt_lay.addWidget(btn_yukle); alt_lay.addWidget(btn_ekle)
        alt_lay.addWidget(btn_birim); alt_lay.addWidget(btn_duzenle); alt_lay.addWidget(btn_sil)
        alt_lay.addStretch(); alt_lay.addWidget(self.lbl_secim)
        alt_lay.addWidget(btn_sheets); alt_lay.addWidget(self.btn_etiket)
        ana.addLayout(alt_lay)
        self.tablo.selectionModel().selectionChanged.connect(self._secim_guncelle)
        self._kat_sec(KATEGORILER[0])

    def _kat_btn_stil(self, aktif):
        if aktif:
            return (f"QPushButton {{background-color:{RENK['metin']};color:white;border:none;"
                    f"border-radius:6px;padding:6px 20px;font-weight:700;font-size:13px;}}")
        return (f"QPushButton {{background-color:{RENK['yuzey2']};color:{RENK['metin2']};"
                f"border:1.5px solid {RENK['cizgi']};border-radius:6px;padding:6px 20px;font-size:13px;}}"
                f"QPushButton:hover{{background-color:{RENK['cizgi']};color:{RENK['metin']};}}")

    def _kat_sec(self, kat):
        self.aktif_kat = kat
        for k, btn in self.kat_butonlar.items():
            btn.setStyleSheet(self._kat_btn_stil(k == kat))
        self.yukle()

    def yukle(self):
        if hasattr(self,'_yt') and self._yt.isRunning(): return
        self._yt = StokYuklemeThread(self.aktif_kat)
        self._yt.bitti.connect(self._yukle_bitti)
        self._yt.start()

    def _yukle_bitti(self, df, depoda, turda, bekleyen, markalar):
        self.df = df
        self.s_toplam.set_deger(len(df))
        self.s_stok.set_deger(depoda)
        self.s_turda.set_deger(turda)
        self.s_bekliyor.set_deger(bekleyen)
        self.cb_marka.blockSignals(True)
        onceki = self.cb_marka.currentText()
        self.cb_marka.clear(); self.cb_marka.addItem('Tüm Markalar')
        self.cb_marka.addItems(markalar)
        idx = self.cb_marka.findText(onceki)
        if idx >= 0: self.cb_marka.setCurrentIndex(idx)
        self.cb_marka.blockSignals(False)
        self._filtrele()

    def _filtrele(self):
        if self.df.empty: self.tablo.setRowCount(0); return
        d = self.df.copy()
        durum = self.cb_durum.currentText()
        marka = self.cb_marka.currentText()
        ara   = self.ara_txt.text().strip().lower()
        if durum == "Etiket Bekliyor": d = d[d["etiket_bekleyen"] > 0]
        elif durum == "Etiketli":      d = d[d["etiket_bekleyen"] == 0]
        if marka != "Tüm Markalar":   d = d[d["marka"] == marka]
        if ara:
            mask = d.astype(str).apply(lambda c: c.str.lower().str.contains(ara, na=False)).any(axis=1)
            d = d[mask]
        self._tabloyu_doldur(d)

    def _tabloyu_doldur(self, d):
        self.tablo.setSortingEnabled(False)
        self.tablo.setRowCount(len(d))
        sutunlar = ["id","kategori","marka","yaygin_ad","motor",
                    "ref1","ref2","ref3","ref4","ref5",
                    "fiyat","depoda_adet","turda_adet","etiket_basildi"]

        for ri, (_, row) in enumerate(d.iterrows()):
            for ci, key in enumerate(sutunlar):
                val = row.get(key, "-")
                # depoda_adet / turda_adet için özel gösterim
                if key == "depoda_adet":
                    val_str = f"{int(val)} adet" if pd.notna(val) else "0 adet"
                elif key == "turda_adet":
                    val_str = f"{int(val)}" if pd.notna(val) and int(val) > 0 else "-"
                elif key == "etiket_basildi":
                    bek = row.get("etiket_bekleyen", 0)
                    val_str = f"⚠ {int(bek)} bekliyor" if bek > 0 else "✓ Tümü etiketli"
                else:
                    val_str = str(val) if not pd.isna(val) else "-"

                item = _NumericItem(val_str) if key == "id" else QTableWidgetItem(val_str)
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

                depoda = row.get("depoda_adet", 0)
                if key == "etiket_basildi":
                    bek = row.get("etiket_bekleyen", 0)
                    item.setForeground(QColor(RENK["aksan"] if bek > 0 else RENK["yesil"]))
                    item.setFont(QFont("", -1, QFont.Weight.Bold))
                elif key == "turda_adet" and int(val or 0) > 0:
                    item.setForeground(QColor(RENK["mavi"]))
                elif depoda <= 0 and key not in ("etiket_basildi", "depoda_adet", "turda_adet"):
                    item.setForeground(QColor(RENK["metin3"]))

                self.tablo.setItem(ri, ci, item)

            # Satır arka planı
            if row.get("depoda_adet", 0) <= 0:
                for c in range(14):
                    it = self.tablo.item(ri, c)
                    if it: it.setBackground(QColor("#FFF8F8"))

        self.tablo.setSortingEnabled(True)

    def _secim_guncelle(self):
        n = len(self.tablo.selectionModel().selectedRows())
        self.lbl_secim.setText(f"{n} satır seçili" if n else "")

    def _get_secili_stok_id(self):
        rows = self.tablo.selectionModel().selectedRows()
        if not rows: return None
        return int(self.tablo.item(rows[0].row(), 0).text())

    def _sag_menu(self, pos):
        if not self.tablo.selectionModel().selectedRows(): return
        menu = QMenu(self)
        menu.addAction("Duzenle", self._duzenle)
        menu.addAction("Birimleri Gor", self._birim_goster)
        menu.addAction("Etiketle", self.etiketle)
        menu.addSeparator()
        menu.addAction("Sil", self.secilenleri_sil)
        menu.exec(self.tablo.viewport().mapToGlobal(pos))

    def _duzenle(self):
        sid = self._get_secili_stok_id()
        if not sid: QMessageBox.information(self,"Bilgi","Once satir secin."); return
        conn = get_conn()
        kayit = conn.execute("SELECT * FROM stok WHERE id=?", (sid,)).fetchone()
        conn.close()
        if not kayit: return
        dlg = StokDialog(self.aktif_kat, kayit=dict(kayit), parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted: return
        d = dlg.get_veri(); d.pop("adet", None)
        ekle_sb = getattr(dlg,"ekle_sb",None)
        cikar_sb= getattr(dlg,"cikar_sb",None)
        if ekle_sb and ekle_sb.value()>0: birim_ekle(sid, ekle_sb.value())
        if cikar_sb and cikar_sb.value()>0:
            conn2=get_conn()
            for b in conn2.execute("SELECT id FROM stok_birimi WHERE stok_id=? AND durum='DEPODA' LIMIT ?",(sid,cikar_sb.value())).fetchall():
                conn2.execute("UPDATE stok_birimi SET durum='SATILDI' WHERE id=?",(b[0],))
            conn2.commit(); conn2.close()
        conn=get_conn()
        conn.execute("UPDATE stok SET kategori=?,marka=?,yaygin_ad=?,motor=?,ref1=?,ref2=?,ref3=?,ref4=?,ref5=?,fiyat=?,guncelleme=datetime('now','localtime') WHERE id=?",
            (d["kategori"],d["marka"],d["yaygin_ad"],d["motor"],d["ref1"],d["ref2"],d["ref3"],d["ref4"],d["ref5"],d["fiyat"],sid))
        conn.commit(); conn.close()
        stok_miktari_guncelle(sid)
        self._silent_sheets_sync()
        self.yukle()

    def _stok_satirlari(self):
        conn = get_conn()
        rows = conn.execute("""SELECT s.id,s.kategori,s.marka,s.yaygin_ad,s.motor,
                   s.ref1,s.ref2,s.ref3,s.ref4,s.ref5,s.fiyat,
                   COALESCE(d.n,0),COALESCE(t.n,0),s.guncelleme
            FROM stok s
            LEFT JOIN (SELECT stok_id,COUNT(*) n FROM stok_birimi WHERE durum='DEPODA' GROUP BY stok_id) d ON d.stok_id=s.id
            LEFT JOIN (SELECT stok_id,COUNT(*) n FROM stok_birimi WHERE durum='TURDA'  GROUP BY stok_id) t ON t.stok_id=s.id
            ORDER BY s.kategori,s.marka,CAST(s.id AS INTEGER)""").fetchall()
        conn.close()
        return [list(r) for r in rows]

    def stok_sheets_gonder(self):
        sheets = get_sheets()
        if not sheets.aktif:
            QMessageBox.warning(self,"Sheets","Ayarlar'dan baglanti kurun."); return
        rows = self._stok_satirlari()
        sheets.stok_genel_yenile(rows)
        QMessageBox.information(self,"Gonderildi",f"{len(rows)} urun Sheets'e eklendi.")

    def _silent_sheets_sync(self):
        """Kullanıcıya bildirim göstermeden arka planda Sheets'e sync eder."""
        sheets = get_sheets()
        if not sheets.aktif: return
        rows = self._stok_satirlari()
        sheets.stok_genel_yenile(rows)

    def _birim_goster(self):
        sid = self._get_secili_stok_id()
        if not sid: QMessageBox.information(self, "Bilgi", "Önce satır seçin."); return
        conn = get_conn()
        stok = conn.execute("SELECT * FROM stok WHERE id=?", (sid,)).fetchone()
        conn.close()
        if not stok: return
        dlg = BirimDialog(sid, stok["marka"], stok["yaygin_ad"], self)
        dlg.exec()
        self.yukle()

    def urun_ekle(self):
        dlg = StokDialog(self.aktif_kat, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted: return
        d = dlg.get_veri()
        adet = d.pop("adet", 1)
        d["stok_miktari"] = adet
        conn = get_conn()
        cursor = conn.execute(
            """INSERT INTO stok (kategori,marka,yaygin_ad,motor,
               ref1,ref2,ref3,ref4,ref5,fiyat,stok_miktari)
               VALUES (:kategori,:marka,:yaygin_ad,:motor,
               :ref1,:ref2,:ref3,:ref4,:ref5,:fiyat,:stok_miktari)""", d)
        stok_id = cursor.lastrowid
        for s in range(1, adet + 1):
            conn.execute("INSERT INTO stok_birimi (stok_id, barkod_id) VALUES (?,?)",
                         (stok_id, f"{stok_id}-{s}"))
        conn.commit(); conn.close()
        self.yukle()

    def secilenleri_sil(self):
        rows = self.tablo.selectionModel().selectedRows()
        if not rows: return
        cevap = QMessageBox.question(self, "Onay",
            f"{len(rows)} ürün ve tüm birimleri silinecek. Emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if cevap != QMessageBox.StandardButton.Yes: return
        ids = [int(self.tablo.item(r.row(), 0).text()) for r in rows]
        conn = get_conn()
        conn.executemany("DELETE FROM stok_birimi WHERE stok_id=?", [(i,) for i in ids])
        conn.executemany("DELETE FROM stok WHERE id=?", [(i,) for i in ids])
        conn.commit(); conn.close(); self.yukle()

    def etiketle(self):
        """Seçili ürünlerin ETİKETSİZ birimlerini toplu etiketle (arka planda)."""
        rows = self.tablo.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(self, "Bilgi", "Önce satır seçin."); return

        # Tüm birim verilerini ana thread'de topla (DB sorguları hızlıdır)
        gorevler = []   # [(barkod_id, stok_id, kat, marka, ad, secili, birim_db_id), ...]
        conn = get_conn()
        for r in rows:
            sid = int(self.tablo.item(r.row(), 0).text())
            stok = conn.execute("SELECT * FROM stok WHERE id=?", (sid,)).fetchone()
            if not stok: continue
            refs = [stok["ref1"],stok["ref2"],stok["ref3"],stok["ref4"],stok["ref5"]]
            refs = [x for x in refs if x and x != "-"]
            dlg = RefSecimDialog(refs, self)
            if dlg.exec() != QDialog.DialogCode.Accepted: continue
            secili = dlg.get_secili()
            birimler = conn.execute(
                "SELECT * FROM stok_birimi WHERE stok_id=? AND etiket_basildi='HAYIR' AND durum='DEPODA'",
                (sid,)).fetchall()
            for birim in birimler:
                gorevler.append((birim["barkod_id"], sid,
                                  stok["kategori"], stok["marka"],
                                  stok["yaygin_ad"], secili, birim["id"]))
        conn.close()

        if not gorevler: return

        # İlerleme dialog'u
        from PyQt6.QtWidgets import QProgressDialog
        progress = QProgressDialog(f"Etiket oluşturuluyor... (0/{len(gorevler)})",
                                   None, 0, len(gorevler), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0); progress.setValue(0)

        self._etiket_threads   = []
        self._etiket_basarili  = 0
        self._etiket_toplam    = len(gorevler)
        self._etiket_bitti_cnt = 0
        self._etiket_progress  = progress

        def _birim_bitti(barkod_id, yol, birim_db_id):
            c = get_conn()
            c.execute("UPDATE stok_birimi SET etiket_basildi='EVET' WHERE id=?", (birim_db_id,))
            c.commit(); c.close()
            yazicilar = yazici_listesi()
            ok, _ = yazici_gonder(yol, yazicilar[0] if yazicilar else None)
            if not ok:
                import subprocess as sp, sys as _sys
                if _sys.platform == "win32": os.startfile(os.path.dirname(yol))
                else: sp.Popen(["xdg-open", os.path.dirname(yol)])
            self._etiket_basarili  += 1
            self._etiket_bitti_cnt += 1
            progress.setValue(self._etiket_bitti_cnt)
            progress.setLabelText(
                f"Etiket oluşturuluyor... ({self._etiket_bitti_cnt}/{self._etiket_toplam})")
            if self._etiket_bitti_cnt >= self._etiket_toplam:
                self.yukle()
                QMessageBox.information(self, "Tamamlandı",
                                        f"✓ {self._etiket_basarili} etiket oluşturuldu.")

        def _birim_hata(barkod_id, mesaj):
            self._etiket_bitti_cnt += 1
            progress.setValue(self._etiket_bitti_cnt)
            QMessageBox.critical(self, "Hata", f"{barkod_id}: {mesaj}")
            if self._etiket_bitti_cnt >= self._etiket_toplam:
                self.yukle()

        # Her birimi kendi thread'inde oluştur (sıralı: bir sonraki bir önceki bitince)
        # Basit yaklaşım: her birimi arka plan thread'inde sırayla işle
        self._etiket_kuyruk = list(gorevler)
        self._etiket_bitti_cb  = _birim_bitti
        self._etiket_hata_cb   = _birim_hata
        self._etiket_progress  = progress
        self._etiket_ileri()

    def _etiket_ileri(self):
        """Kuyruktaki bir sonraki birimi thread'de işler."""
        if not self._etiket_kuyruk: return
        barkod_id, sid, kat, marka, ad, secili, birim_db_id = self._etiket_kuyruk.pop(0)
        t = EtiketThread(barkod_id, sid, kat, marka, ad, secili)
        def _bitti(bid, yol, dbid=birim_db_id):
            self._etiket_bitti_cb(bid, yol, dbid)
            self._etiket_ileri()
        def _hata(bid, msg):
            self._etiket_hata_cb(bid, msg)
            self._etiket_ileri()
        t.bitti.connect(_bitti)
        t.hata.connect(_hata)
        self._etiket_threads.append(t)
        t.start()

    def import_csv(self):
        dosyalar, _ = QFileDialog.getOpenFileNames(
            self, "CSV Seç", "", "CSV (*.csv)",
            options=QFileDialog.Option.DontUseNativeDialog)
        if not dosyalar: return
        dlg = QProgressDialog("Yükleniyor...", "İptal", 0, 100, self)
        dlg.setWindowModality(Qt.WindowModality.WindowModal); dlg.show()
        self.import_thread = ImportThread(dosyalar, self.aktif_kat)
        self.import_thread.ilerleme.connect(lambda y, t: dlg.setValue(int(y/t*100)))
        self.import_thread.bitti.connect(lambda ek, at: (
            dlg.close(),
            QMessageBox.information(self, "Tamam", f"✓ {ek} ürün eklendi, {at} atlandı."),
            self.yukle()))
        self.import_thread.hata.connect(lambda e: (dlg.close(), QMessageBox.critical(self,"Hata",e)))
        self.import_thread.start()

    def sablon_indir(self):
        kaydet, _ = QFileDialog.getSaveFileName(
            self, "Kaydet", f"sablon_{self.aktif_kat}.csv", "CSV (*.csv)",
            options=QFileDialog.Option.DontUseNativeDialog)
        if not kaydet: return
        import csv
        with open(kaydet, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["Ürün Grubu/Marka","Yaygın Ad","Motor Bilgisi",
                        "Marka Ref No","Ref No","Ref No.1","Ref No.2","Ref No.3",
                        "Fiyat","Stok Durumu"])
            w.writerow(["Renault","TA2000","1.6","S1234","8200xxx","","","","3500","3"])
        QMessageBox.information(self, "Tamam", f"Şablon kaydedildi:\n{kaydet}")
