"""
core/sheets.py  —  OAuth2 (Desktop) akışı
Servis hesabı JSON gerektirmez.
İlk çalıştırmada tarayıcı açılır → onay → token kaydedilir.
"""
import os, json, threading, queue, time
from datetime import datetime

_BASE         = os.path.dirname(os.path.dirname(__file__))
CLIENT_SECRET = os.path.join(_BASE, "assets", "client_secret.json")
TOKEN_PATH    = os.path.join(_BASE, "assets", "oauth_token.json")
CONFIG_PATH   = os.path.join(_BASE, "assets", "sheets_config.json")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

TAB = {
    "stok":      "Stok_Genel",
    "cikanlar":  "Tura_Cikanlar",
    "donuslar":  "Tur_Donuşlar",
    "program":   "Tur_Programi",
    "anlık":     "Stok_Anlık",
    "satislar":  "Satışlar",
    "mal_giris": "Mal_Girişleri",
}

HEADERS = {
    "stok":      ["ID","Kategori","Marka","Yaygın Ad","Motor",
                  "Ref1","Ref2","Ref3","Ref4","Ref5",
                  "Fiyat","Stok","Etiket","Güncelleme"],
    "cikanlar":  ["Zaman","Tur Adı","Stok ID","Kategori","Marka","Yaygın Ad","Ref1","Barkod"],
    "donuslar":  ["Zaman","Tur Adı","Stok ID","Kategori","Marka","Yaygın Ad","Durum","Not"],
    "program":   ["Tur Adı","Başlangıç","Bitiş","Durum","Notlar","Oluşturma"],
    "anlık":     ["Zaman","Kategori","Marka","Stok Adedi"],
    "satislar":  ["Zaman","Stok ID","Kategori","Marka","Yaygın Ad","Ref1",
                  "Adet","Birim Fiyat","Toplam Tutar","Müşteri","Not","Stok Sonrası"],
    "mal_giris": ["Zaman","Stok ID","Kategori","Marka","Yaygın Ad",
                  "Giren Adet","Giriş Fiyatı","Tedarikçi","Not","Stok Sonrası"],
}


def _oauth_baglan():
    import gspread
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request

    creds = None
    if os.path.exists(TOKEN_PATH):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        except Exception:
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None
        if not creds:
            if not os.path.exists(CLIENT_SECRET):
                raise FileNotFoundError(
                    "assets/client_secret.json bulunamadı!\n"
                    "Google Cloud Console → OAuth 2.0 Client ID (Desktop app) → İndir")
            flow  = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET, SCOPES)
            creds = flow.run_local_server(port=0, open_browser=True)
        os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())

    return gspread.authorize(creds)


class SheetsManager:
    def __init__(self):
        self._gc       = None
        self._sheet    = None
        self._tabs     = {}
        self._aktif    = False
        self._queue    = queue.Queue()
        self._thread   = None
        self.sheet_url = ""
        self.hata_msg  = ""
        self._config_yukle()
        if self._aktif:
            self._baslat()

    def _config_yukle(self):
        if not os.path.exists(CLIENT_SECRET):
            self.hata_msg = "client_secret.json bulunamadı — Sheets devre dışı."
            return
        if os.path.exists(CONFIG_PATH):
            try:
                self.sheet_url = json.load(open(CONFIG_PATH)).get("sheet_url", "")
            except Exception:
                pass
        if not self.sheet_url:
            self.hata_msg = "Sheet URL ayarlanmamış."
            return
        self._aktif = True

    def config_kaydet(self, sheet_url: str):
        self.sheet_url = sheet_url
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            json.dump({"sheet_url": sheet_url}, f)
        self._aktif   = True
        self.hata_msg = ""
        self._baslat()

    def token_sil(self):
        if os.path.exists(TOKEN_PATH):
            os.remove(TOKEN_PATH)
        self.hata_msg = "Token silindi. Yeniden bağlanın."

    def _baslat(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def _baglan(self) -> bool:
        try:
            self._gc    = _oauth_baglan()
            self._sheet = self._gc.open_by_url(self.sheet_url)
            self._tab_hazirla()
            self.hata_msg = ""
            return True
        except FileNotFoundError as e:
            self.hata_msg = str(e)
            return False
        except ImportError:
            self.hata_msg = "Eksik: pip install gspread google-auth-oauthlib"
            return False
        except Exception as e:
            self.hata_msg = f"Bağlantı hatası: {e}"
            return False

    def _tab_hazirla(self):
        mevcut = {ws.title: ws for ws in self._sheet.worksheets()}
        for key, ad in TAB.items():
            if ad not in mevcut:
                ws = self._sheet.add_worksheet(title=ad, rows=5000, cols=20)
                if key in HEADERS:
                    ws.append_row(HEADERS[key], value_input_option="RAW")
                self._tabs[key] = ws
            else:
                self._tabs[key] = mevcut[ad]
                try:
                    if not self._tabs[key].row_values(1) and key in HEADERS:
                        self._tabs[key].append_row(HEADERS[key])
                except Exception:
                    pass

    def _worker(self):
        bagli = False
        while True:
            try:
                gorev = self._queue.get(timeout=30)
                if not bagli:
                    bagli = self._baglan()
                if bagli and gorev:
                    gorev()
                elif not bagli:
                    self._queue.put(gorev)
                    time.sleep(10)
            except queue.Empty:
                pass
            except Exception as e:
                bagli = False
                self.hata_msg = str(e)
                time.sleep(10)

    def _kuyruga_ekle(self, fn):
        if self._aktif:
            self._queue.put(fn)

    def _satir_ekle(self, tab_key: str, satir: list):
        def _yaz():
            ws = self._tabs.get(tab_key)
            if ws:
                ws.append_row(satir, value_input_option="USER_ENTERED")
        self._kuyruga_ekle(_yaz)

    # ── Public API ────────────────────────────────────────────────────────
    def tura_cikis_ekle(self, tur_adi, stok_id, kategori, marka, yaygin_ad, ref1, barkod):
        self._satir_ekle("cikanlar", [datetime.now().strftime("%d.%m.%Y %H:%M"),
            tur_adi, stok_id, kategori, marka, yaygin_ad, ref1, str(barkod)])

    def tur_donus_ekle(self, tur_adi, stok_id, kategori, marka, yaygin_ad, durum, not_=""):
        self._satir_ekle("donuslar", [datetime.now().strftime("%d.%m.%Y %H:%M"),
            tur_adi, stok_id, kategori, marka, yaygin_ad, durum, not_])

    def tur_programi_ekle(self, tur_adi, baslangic, bitis, durum, notlar):
        self._satir_ekle("program", [tur_adi, baslangic, bitis, durum, notlar,
            datetime.now().strftime("%d.%m.%Y %H:%M")])

    def tur_programi_guncelle(self, tur_adi, yeni_durum):
        def _g():
            ws = self._tabs.get("program")
            if not ws: return
            for i, row in enumerate(ws.get_all_values()[1:], start=2):
                if row and row[0] == tur_adi:
                    ws.update_cell(i, 4, yeni_durum); break
        self._kuyruga_ekle(_g)

    def stok_anlık_guncelle(self, liste):
        z = datetime.now().strftime("%d.%m.%Y %H:%M")
        rows = [[z, k, m, str(a)] for k, m, a in liste]
        def _y():
            ws = self._tabs.get("anlık")
            if ws and rows:
                ws.append_rows(rows, value_input_option="USER_ENTERED")
        self._kuyruga_ekle(_y)

    def stok_genel_yenile(self, satirlar: list):
        def _y():
            ws = self._tabs.get("stok")
            if not ws: return
            if ws.row_count > 1:
                ws.batch_clear([f"A2:Z{ws.row_count}"])
            if satirlar:
                ws.append_rows(satirlar, value_input_option="USER_ENTERED")
        self._kuyruga_ekle(_y)

    def satis_ekle(self, stok_id, kategori, marka, yaygin_ad, ref1,
                   adet, birim_fiyat, toplam, musteri, not_, stok_sonrasi):
        self._satir_ekle("satislar", [datetime.now().strftime("%d.%m.%Y %H:%M"),
            stok_id, kategori, marka, yaygin_ad, ref1,
            adet, birim_fiyat, toplam, musteri, not_, stok_sonrasi])

    def mal_giris_ekle(self, stok_id, kategori, marka, yaygin_ad,
                       adet, giris_fiyati, tedarikci, not_, stok_sonrasi):
        self._satir_ekle("mal_giris", [datetime.now().strftime("%d.%m.%Y %H:%M"),
            stok_id, kategori, marka, yaygin_ad,
            adet, giris_fiyati, tedarikci, not_, stok_sonrasi])

    @property
    def bagli(self):
        return self._aktif and not self.hata_msg

    @property
    def aktif(self):
        return self._aktif


_instance = None

def get_sheets() -> SheetsManager:
    global _instance
    if _instance is None:
        _instance = SheetsManager()
    return _instance
