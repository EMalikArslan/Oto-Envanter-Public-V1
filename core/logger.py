"""
core/logger.py
==============
Ares Envanter — Merkezi Loglama & Watchdog Sistemi

Özellikler:
  - Tüm hatalar logs/ares.log dosyasına yazılır
  - UI freeze tespit edilirse log kaydedilir
  - Çökme anında tam traceback + sistem bilgisi kaydedilir
  - Log dosyası 5MB üzerine çıkınca rotate edilir (5 yedek tutulur)
  - Uygulama her açılışta eski log özeti ekrana gösterir (hata varsa)
"""

import os, sys, logging, traceback, threading, time, platform
from datetime import datetime
from logging.handlers import RotatingFileHandler

# ── Log klasörü ────────────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LOG_DIR  = os.path.join(BASE_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "ares.log")
os.makedirs(LOG_DIR, exist_ok=True)


# ── Logger kurulum ─────────────────────────────────────────────────────────
def _kur_logger() -> logging.Logger:
    logger = logging.getLogger("ares")
    if logger.handlers:          # zaten kurulmuşsa tekrar kurma
        return logger

    logger.setLevel(logging.DEBUG)

    # Dosyaya yaz — 5MB, 5 yedek
    dosya_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024,
        backupCount=5, encoding="utf-8")
    dosya_handler.setLevel(logging.DEBUG)
    dosya_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"))

    # Konsola yaz — sadece WARNING+
    konsol_handler = logging.StreamHandler(sys.stdout)
    konsol_handler.setLevel(logging.WARNING)
    konsol_handler.setFormatter(logging.Formatter(
        "[%(levelname)s] %(message)s"))

    logger.addHandler(dosya_handler)
    logger.addHandler(konsol_handler)
    return logger


log = _kur_logger()


# ── Genel exception handler ────────────────────────────────────────────────
def _global_exception_handler(exc_type, exc_value, exc_tb):
    """Yakalanmayan tüm exceptionları loglar."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return

    tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    log.critical(
        f"YAKALANMAYAN HATA\n"
        f"{'='*60}\n"
        f"Sistem: {platform.system()} {platform.release()} | "
        f"Python: {sys.version.split()[0]}\n"
        f"{tb_str}"
        f"{'='*60}"
    )

    # Kullanıcıya göster (Qt varsa)
    try:
        from PyQt6.QtWidgets import QMessageBox, QApplication
        if QApplication.instance():
            msg = QMessageBox()
            msg.setWindowTitle("Beklenmeyen Hata")
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setText(
                f"Bir hata oluştu ve kaydedildi.\n\n"
                f"Hata: {exc_type.__name__}: {exc_value}\n\n"
                f"Log dosyası: {LOG_FILE}")
            msg.setDetailedText(tb_str)
            msg.exec()
    except Exception:
        pass


sys.excepthook = _global_exception_handler


# ── Thread exception handler (Python 3.8+) ────────────────────────────────
def _thread_exception_handler(args):
    log.error(
        f"Thread hatası [{args.thread.name}]\n"
        + "".join(traceback.format_exception(
            args.exc_type, args.exc_value, args.exc_tb)))

threading.excepthook = _thread_exception_handler


# ── UI Watchdog ────────────────────────────────────────────────────────────
class UIWatchdog:
    """
    Ana UI thread'ini izler.
    Belirtilen süreden fazla yanıt vermezse log yazar.
    Donma tespiti: her X saniyede bir sinyal gönderilir,
    UI thread bu sinyali alıp 'canlı' olduğunu bildirir.
    """

    def __init__(self, esik_saniye: float = 5.0):
        self._esik    = esik_saniye
        self._son_ok  = time.time()
        self._aktif   = False
        self._thread  = None
        self._don_sayaci = 0

    def kalp_ati(self):
        """UI thread her N ms'de bunu çağırır — 'ben yaşıyorum' sinyali."""
        self._son_ok = time.time()

    def baslat(self):
        self._aktif = True
        self._thread = threading.Thread(
            target=self._izle, daemon=True, name="UIWatchdog")
        self._thread.start()
        log.info("UIWatchdog başlatıldı (eşik: %.1fs)", self._esik)

    def durdur(self):
        self._aktif = False

    def _izle(self):
        while self._aktif:
            time.sleep(1.0)
            gecen = time.time() - self._son_ok
            if gecen > self._esik:
                self._don_sayaci += 1
                log.warning(
                    "UI DONMASI TESPİT EDİLDİ! "
                    "%.1f saniyedir yanıt yok (Don #%d)",
                    gecen, self._don_sayaci)
            elif self._don_sayaci > 0:
                log.info("UI normale döndü (don süresi: ~%.1fs)", gecen)
                self._don_sayaci = 0


# ── Başlangıç özeti ────────────────────────────────────────────────────────
def baslangic_logu():
    """Uygulama başlarken çalıştırılır."""
    log.info(
        f"\n{'='*60}\n"
        f"  ARES ENVANTER BAŞLADI\n"
        f"  Zaman   : {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
        f"  Sistem  : {platform.system()} {platform.release()}\n"
        f"  Python  : {sys.version.split()[0]}\n"
        f"  Klasör  : {BASE_DIR}\n"
        f"{'='*60}"
    )


def son_hatalari_oku(satir_sayisi: int = 50) -> str:
    """Son N satır log döner — başlangıçta hata özeti için."""
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            satirlar = f.readlines()
        hatalar = [s for s in satirlar if
                   "ERROR" in s or "CRITICAL" in s or "WARNING" in s]
        if not hatalar:
            return ""
        return "".join(hatalar[-satir_sayisi:])
    except Exception:
        return ""


# ── Modül düzeyinde log fonksiyonları (kolay kullanım) ────────────────────
def debug(msg, *a, **kw):   log.debug(msg, *a, **kw)
def info(msg, *a, **kw):    log.info(msg, *a, **kw)
def warning(msg, *a, **kw): log.warning(msg, *a, **kw)
def error(msg, *a, **kw):   log.error(msg, *a, **kw)

def hata_yakala(islem_adi: str):
    """
    Dekoratör: fonksiyon hata verirse logla, uygulamayı çökertme.

    Kullanım:
        @hata_yakala("stok yükleme")
        def yukle(self):
            ...
    """
    def dekorator(func):
        def sarici(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                log.error(
                    "%s sırasında hata: %s\n%s",
                    islem_adi, e, traceback.format_exc())
        return sarici
    return dekorator


# Singleton watchdog
watchdog = UIWatchdog(esik_saniye=8.0)
