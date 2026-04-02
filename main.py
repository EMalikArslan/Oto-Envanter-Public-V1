import sys, os
import core.logger as ares_log
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QStackedWidget, QFrame, QSizePolicy, QSpacerItem,
    QLineEdit, QMessageBox, QScrollArea, QTextBrowser
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QPixmap, QIcon

from core.database import init_db
from core.tema import RENK, BOYUT, get_stylesheet
from core.widgets import AyiriciCizgi
from core.sheets import get_sheets
from modules.stok import StokSayfasi
from modules.tur import TurSayfasi
from modules.hareketler import HareketlerSayfasi
from modules.genel import GenelSayfasi
from modules.musteri import MusteriSayfasi
from modules.kargo import KargoSayfasi

# Diğer modüller ilerleyen aşamalarda buraya eklenir
# from modules.genel import GenelSayfasi
# from modules.musteri import MusteriSayfasi
# from modules.kargo import KargoSayfasi

LOGO_PATH = os.path.join(os.path.dirname(__file__), "assets", "logo.png")

NAV_ITEMS = [
    ("stok",       "●  Stok & Etiket",   "Ürün yönetimi"),
    ("hareketler", "●  Satış & Giriş",   "Satış kasası & mal girişi"),
    ("tur",        "●  Tur Yönetimi",    "Araç çıkış / dönüş"),
    ("genel",      "●  Genel Durum",     "İstatistik & eksikler"),
    ("musteri",    "●  Müşteriler",      "Müşteri listesi"),
    ("kargo",      "●  Kargo",           "Gönderim & etiket"),
    ("ayarlar",    "⚙  Ayarlar",         "Sistem yapılandırması"),
]


class Sidebar(QWidget):
    def __init__(self, on_navigate):
        super().__init__()
        self.setObjectName("Sidebar")
        self.setFixedWidth(BOYUT["sidebar_w"])
        self.on_navigate = on_navigate
        self.nav_butonlar = {}
        self.aktif = None
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # ── Logo alanı ─────────────────────────────────────────────────
        logo_widget = QWidget()
        logo_widget.setFixedHeight(90)
        logo_widget.setStyleSheet(f"background-color: {RENK['koyu_zemin']};")
        logo_lay = QVBoxLayout(logo_widget)
        logo_lay.setContentsMargins(20, 16, 20, 12)
        logo_lay.setSpacing(2)

        if os.path.exists(LOGO_PATH):
            pix = QPixmap(LOGO_PATH).scaledToWidth(
                120, Qt.TransformationMode.SmoothTransformation)
            lbl_img = QLabel()
            lbl_img.setPixmap(pix)
            lbl_img.setStyleSheet("background: transparent; border: none;")
            logo_lay.addWidget(lbl_img, alignment=Qt.AlignmentFlag.AlignLeft)
        else:
            lbl_a = QLabel("ARES")
            lbl_a.setObjectName("SidebarLogo")
            logo_lay.addWidget(lbl_a)

        lbl_s = QLabel("ENVANTER SİSTEMİ")
        lbl_s.setObjectName("SidebarAlt")
        logo_lay.addWidget(lbl_s)
        lay.addWidget(logo_widget)

        # İnce ayırıcı çizgi
        cizgi = QFrame()
        cizgi.setFixedHeight(1)
        cizgi.setStyleSheet(f"background-color: #2E2C29;")
        lay.addWidget(cizgi)

        # ── Navigasyon butonları ────────────────────────────────────────
        nav_container = QWidget()
        nav_container.setStyleSheet(f"background-color: {RENK['koyu_zemin']};")
        nav_lay = QVBoxLayout(nav_container)
        nav_lay.setContentsMargins(10, 16, 10, 16)
        nav_lay.setSpacing(4)

        section_lbl = QLabel("MODÜLLER")
        section_lbl.setStyleSheet(
            f"color: #4A4845; font-size: 10px; font-weight: 700; "
            f"letter-spacing: 2px; padding: 0 8px 8px 8px;")
        nav_lay.addWidget(section_lbl)

        for key, baslik, alt in NAV_ITEMS:
            btn = QPushButton(baslik)
            btn.setObjectName("NavBtn")
            btn.setFixedHeight(42)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self.git(k))
            btn.setToolTip(alt)
            nav_lay.addWidget(btn)
            self.nav_butonlar[key] = btn

        nav_lay.addStretch()
        lay.addWidget(nav_container, 1)

        # ── Alt bilgi ──────────────────────────────────────────────────
        alt_widget = QWidget()
        alt_widget.setFixedHeight(56)
        alt_widget.setStyleSheet(
            f"background-color: {RENK['koyu_zemin']}; "
            f"border-top: 1px solid #2E2C29;")
        alt_lay = QVBoxLayout(alt_widget)
        alt_lay.setContentsMargins(20, 8, 20, 8)
        versiyon = QLabel("v1.0  —  Ares Company Partners")
        versiyon.setStyleSheet(
            f"color: #3A3834; font-size: 10px; letter-spacing: 0.5px;")
        alt_lay.addWidget(versiyon)
        lay.addWidget(alt_widget)

    def git(self, key):
        self.aktif_yap(key)
        self.on_navigate(key)

    def aktif_yap(self, key):
        if self.aktif:
            b = self.nav_butonlar.get(self.aktif)
            if b:
                b.setProperty("active", False)
                b.setStyle(b.style())
        self.aktif = key
        b = self.nav_butonlar.get(key)
        if b:
            b.setProperty("active", True)
            b.setStyle(b.style())


class ContentArea(QWidget):
    """Sağ içerik alanı: header + stacked modüller."""
    def __init__(self):
        super().__init__()
        self.modüller = {}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # ── Header ─────────────────────────────────────────────────────
        self.header = QWidget()
        self.header.setObjectName("Header")
        self.header.setFixedHeight(BOYUT["header_h"])
        h_lay = QHBoxLayout(self.header)
        h_lay.setContentsMargins(24, 0, 24, 0)

        self.lbl_baslik = QLabel("Stok & Etiket")
        self.lbl_baslik.setObjectName("HeaderBaslik")

        self.lbl_alt = QLabel("ÜRÜN YÖNETİMİ")
        self.lbl_alt.setObjectName("HeaderAlt")

        sol = QVBoxLayout()
        sol.setSpacing(2)
        sol.addWidget(self.lbl_baslik)
        sol.addWidget(self.lbl_alt)
        h_lay.addLayout(sol)
        h_lay.addStretch()
        lay.addWidget(self.header)

        # Header alt çizgisi
        cizgi = QFrame()
        cizgi.setFixedHeight(1)
        cizgi.setStyleSheet(f"background-color: {RENK['cizgi']};")
        lay.addWidget(cizgi)

        # ── Stacked içerik ─────────────────────────────────────────────
        self.stack = QStackedWidget()
        lay.addWidget(self.stack, 1)

        # Modülleri yükle
        self._modul_tanim = {
            "stok":       (StokSayfasi,       "Stok & Etiket",   "ÜRÜN YÖNETİMİ"),
            "hareketler": (HareketlerSayfasi, "Satış & Giriş",   "SATIŞ KASASI & MAL GİRİŞİ"),
            "tur":        (TurSayfasi,        "Tur Yönetimi",    "ARAÇ ÇIKIŞ & DÖNÜŞ"),
            "genel":      (GenelSayfasi,      "Genel Durum",     "İSTATİSTİK & EKSİK LİSTESİ"),
            "musteri":    (MusteriSayfasi,    "Müşteriler",      "MÜŞTERİ LİSTESİ & BORÇ TAKİBİ"),
            "kargo":      (KargoSayfasi,      "Kargo",           "GÖNDERİM & ETİKET"),
            "ayarlar":    (AyarSayfasi,       "Ayarlar",         "SİSTEM YAPILANDIRMASI"),
        }
        self._modul_ekle("stok", StokSayfasi(), "Stok & Etiket", "ÜRÜN YÖNETİMİ")

    def _modul_ekle(self, key, widget, baslik, alt):
        self.modüller[key] = (widget, baslik, alt)
        self.stack.addWidget(widget)

    def _placeholder(self, key, baslik, mesaj):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl = QLabel(mesaj)
        lbl.setStyleSheet(
            f"font-size: 22px; font-weight: 700; color: {RENK['cizgi_koyu']};")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(lbl)
        self.modüller[key] = (w, baslik, baslik.upper())
        self.stack.addWidget(w)

    def goster(self, key):
        if key not in self.modüller and key in getattr(self,"_modul_tanim",{}):
            sinif,baslik,alt = self._modul_tanim[key]
            try: self._modul_ekle(key, sinif(), baslik, alt)
            except Exception as e:
                import core.logger as l; l.error("Modul yuklenemedi %s: %s",key,e); return
        if key not in self.modüller: return
        widget,baslik,alt = self.modüller[key]
        self.stack.setCurrentWidget(widget)
        self.lbl_baslik.setText(baslik)
        self.lbl_alt.setText(alt)


class AyarSayfasi(QWidget):
    """Google Sheets yapılandırması ve sistem ayarları."""
    def __init__(self):
        super().__init__()
        self._build()

    def _build(self):
        from PyQt6.QtWidgets import QScrollArea, QTextBrowser
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 24, 32, 24)
        lay.setSpacing(20)

        # Başlık
        lbl = QLabel("Google Sheets Yapılandırması")
        lbl.setStyleSheet("font-size: 18px; font-weight: 700;")
        lay.addWidget(lbl)
        lay.addWidget(AyiriciCizgi())

        # Mevcut durum
        sheets = get_sheets()
        durum_frame = QFrame()
        durum_frame.setObjectName("Kart")
        durum_frame.setStyleSheet(
            f"QFrame#Kart {{ background: {RENK['yuzey']}; border-radius: 10px; "
            f"border: 1px solid {RENK['cizgi']}; padding: 4px; }}")
        df_lay = QHBoxLayout(durum_frame)
        df_lay.setContentsMargins(16, 12, 16, 12)

        if sheets.aktif and not sheets.hata_msg:
            durum_txt = f"● Bağlı"
            durum_stil = f"font-size: 14px; font-weight: 700; color: {RENK['yesil']};"
        else:
            durum_txt = f"○ Bağlı Değil — {sheets.hata_msg or 'Yapılandırılmamış'}"
            durum_stil = f"font-size: 14px; font-weight: 700; color: {RENK['aksan']};"

        lbl_durum = QLabel(durum_txt)
        lbl_durum.setStyleSheet(durum_stil)
        df_lay.addWidget(lbl_durum)
        df_lay.addStretch()
        lay.addWidget(durum_frame)

        # Sheet URL girişi
        url_lay = QHBoxLayout()
        lbl_url = QLabel("Google Sheet URL:")
        lbl_url.setFixedWidth(160)
        lbl_url.setStyleSheet(f"font-weight: 600; font-size: 13px;")
        self.txt_url = QLineEdit()
        self.txt_url.setMinimumHeight(40)
        self.txt_url.setPlaceholderText(
            "https://docs.google.com/spreadsheets/d/XXXXXXX/edit")
        if sheets.sheet_url:
            self.txt_url.setText(sheets.sheet_url)
        url_lay.addWidget(lbl_url)
        url_lay.addWidget(self.txt_url)
        lay.addLayout(url_lay)

        btn_lay2 = QHBoxLayout()
        btn_kaydet = QPushButton("Kaydet & Bağlan")
        btn_kaydet.setObjectName("BtnAksan")
        btn_kaydet.setFixedWidth(180)
        btn_kaydet.clicked.connect(self._kaydet)
        btn_token = QPushButton("Google Oturumunu Sıfırla")
        btn_token.setObjectName("BtnIkincil")
        btn_token.setFixedWidth(220)
        btn_token.clicked.connect(self._token_sil)
        btn_lay2.addWidget(btn_kaydet)
        btn_lay2.addWidget(btn_token)
        btn_lay2.addStretch()
        lay.addLayout(btn_lay2)
        lay.addWidget(AyiriciCizgi())

        # Adım adım rehber
        rehber_lbl = QLabel("Kurulum Rehberi")
        rehber_lbl.setStyleSheet("font-size: 15px; font-weight: 700;")
        lay.addWidget(rehber_lbl)

        rehber = QLabel("""<ol style='line-height: 2; font-size: 13px;'>
<li><b>console.cloud.google.com</b> → Kişisel Gmail ile giriş → Yeni proje oluştur</li>
<li><b>APIs &amp; Services → Library</b> → <b>Google Sheets API</b> etkinleştir</li>
<li><b>APIs &amp; Services → Library</b> → <b>Google Drive API</b> etkinleştir</li>
<li><b>OAuth consent screen</b> → External → Uygulama adı → Test kullanıcısına Gmail ekle</li>
<li><b>Credentials → + CREATE → OAuth 2.0 Client ID → Desktop app</b> → İndir</li>
<li>İndirilen JSON'ı <b>assets/client_secret.json</b> olarak kaydet</li>
<li>sheets.google.com'da yeni tablo aç → URL'yi altta yapıştır → Kaydet</li>
<li>İlk sync'te tarayıcı açılır → Google hesabınla onay ver → Tamamdır!</li>
</ol>""")
        rehber.setOpenExternalLinks(True)
        rehber.setWordWrap(True)
        rehber.setStyleSheet(f"color: {RENK['metin']}; background: transparent;")
        lay.addWidget(rehber)
        lay.addStretch()

    def _kaydet(self):
        url = self.txt_url.text().strip()
        if not url.startswith("https://docs.google.com/spreadsheets"):
            QMessageBox.warning(self, "Uyarı",
                "Geçerli bir Google Sheets URL'si girin.")
            return
        import os
        secret = os.path.join(os.path.dirname(__file__), "assets", "client_secret.json")
        if not os.path.exists(secret):
            QMessageBox.warning(self, "Uyarı",
                "assets/client_secret.json bulunamadı!\n\n"
                "Google Cloud Console → Credentials →\n"
                "OAuth 2.0 Client IDs → Desktop app → İndir\n"
                "→ assets/client_secret.json olarak kaydedin.")
            return
        get_sheets().config_kaydet(url)
        QMessageBox.information(self, "Tamam",
            "✓ URL kaydedildi!\n\n"
            "Uygulama ilk veri gönderdiğinde tarayıcı açılacak,\n"
            "Google hesabınızla onay verin. Bir kez yeterli.")

    def _token_sil(self):
        cevap = QMessageBox.question(self, "Token Sil",
            "Kaydedilmiş Google oturumu silinecek.\nBir sonraki sync'te tekrar onay istenecek.\nEmin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if cevap == QMessageBox.StandardButton.Yes:
            get_sheets().token_sil()
            QMessageBox.information(self, "Tamam", "Token silindi.")


class AresApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ares Envanter Sistemi")
        self.resize(1360, 860)
        self.setMinimumSize(1100, 700)

        init_db()

        # ── Ana layout: Sidebar | İçerik ───────────────────────────────
        merkez = QWidget()
        self.setCentralWidget(merkez)
        lay = QHBoxLayout(merkez)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.content = ContentArea()
        self.sidebar = Sidebar(self._navigate)
        lay.addWidget(self.sidebar)

        # Sidebar sağ kenar çizgisi
        separator = QFrame()
        separator.setFixedWidth(1)
        separator.setStyleSheet(f"background-color: {RENK['cizgi']};")
        lay.addWidget(separator)

        lay.addWidget(self.content, 1)

        # Başlangıç: stok
        self.sidebar.git("stok")

    def _navigate(self, key):
        self.content.goster(key)


def main():
    ares_log.baslangic_logu()
    app = QApplication(sys.argv)
    app.setApplicationName("Ares Envanter")
    app.setOrganizationName("Ares Company Partners")
    app.setStyleSheet(get_stylesheet())

    # Font ayarı
    font = QFont("Ubuntu", 13)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(font)

    win = AresApp()
    win.show()
    ares_log.watchdog.baslat()
    from PyQt6.QtCore import QTimer as _QT
    _t=_QT(); _t.timeout.connect(ares_log.watchdog.kalp_ati); _t.start(2000)
    code=app.exec()
    ares_log.watchdog.durdur()
    ares_log.log.info('Uygulama kapandi')
    sys.exit(code)


if __name__ == "__main__":
    main()
