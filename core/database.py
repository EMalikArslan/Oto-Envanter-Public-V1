import sqlite3, os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ares.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()

    # ── STOK (ürün tanımları — adet bilgisi YOK, bireysel parçalar stok_birimi'nde) ──
    c.execute("""CREATE TABLE IF NOT EXISTS stok (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        kategori        TEXT NOT NULL,
        marka           TEXT NOT NULL DEFAULT '-',
        yaygin_ad       TEXT NOT NULL DEFAULT '-',
        motor           TEXT DEFAULT '-',
        ref1 TEXT DEFAULT '-', ref2 TEXT DEFAULT '-',
        ref3 TEXT DEFAULT '-', ref4 TEXT DEFAULT '-', ref5 TEXT DEFAULT '-',
        fiyat           TEXT DEFAULT '-',
        stok_miktari    INTEGER DEFAULT 0,  -- geriye dönük uyumluluk + hızlı okuma
        etiket_basildi  TEXT DEFAULT 'HAYIR',
        olusturma       TEXT DEFAULT (datetime('now','localtime')),
        guncelleme      TEXT DEFAULT (datetime('now','localtime'))
    )""")

    # ── STOK BİRİMİ (her fiziksel parça — kendine ait barkod) ──────────────
    # barkod_id: "99-1", "99-2" formatında — etiket üstünde bu basılır
    c.execute("""CREATE TABLE IF NOT EXISTS stok_birimi (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        stok_id         INTEGER NOT NULL REFERENCES stok(id) ON DELETE CASCADE,
        barkod_id       TEXT NOT NULL UNIQUE,  -- örn: "99-1", "99-2"
        durum           TEXT DEFAULT 'DEPODA', -- DEPODA / TURDA / SATILDI / KAYIP
        etiket_basildi  TEXT DEFAULT 'HAYIR',
        tur_id          INTEGER REFERENCES tur(id),
        giris_tarihi    TEXT DEFAULT (datetime('now','localtime')),
        cikis_tarihi    TEXT,
        notlar          TEXT DEFAULT ''
    )""")

    # ── MÜŞTERİ ───────────────────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS musteri (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        dukkan_adi      TEXT NOT NULL,
        yetkili_adi     TEXT DEFAULT '-',
        il              TEXT DEFAULT '-',
        ilce            TEXT DEFAULT '-',
        adres           TEXT DEFAULT '-',
        telefon         TEXT DEFAULT '-',
        email           TEXT DEFAULT '-',
        urun_gruplari   TEXT DEFAULT '-',
        borc            REAL DEFAULT 0.0,
        notlar          TEXT DEFAULT '',
        olusturma       TEXT DEFAULT (datetime('now','localtime'))
    )""")

    # ── TUR ───────────────────────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS tur (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        tur_adi         TEXT NOT NULL,
        baslangic_tarihi TEXT,
        bitis_tarihi    TEXT,
        durum           TEXT DEFAULT 'BEKLIYOR',
        notlar          TEXT DEFAULT '',
        olusturma       TEXT DEFAULT (datetime('now','localtime'))
    )""")

    # ── TUR ÜRÜN HAREKETLERİ (birim bazlı) ────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS tur_urun (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        tur_id          INTEGER NOT NULL REFERENCES tur(id),
        stok_id         INTEGER NOT NULL REFERENCES stok(id),
        birim_id        INTEGER REFERENCES stok_birimi(id),  -- hangi fiziksel parça
        barkod_id       TEXT,                                -- örn: "99-1"
        cikis_zamani    TEXT,
        donus_zamani    TEXT,
        durum           TEXT DEFAULT 'YUKLU',
        notlar          TEXT DEFAULT ''
    )""")

    # ── KARGO ─────────────────────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS kargo (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        musteri_id      INTEGER REFERENCES musteri(id),
        alici_adi       TEXT NOT NULL,
        alici_adres     TEXT NOT NULL,
        alici_telefon   TEXT DEFAULT '-',
        icerik          TEXT DEFAULT '-',
        takip_no        TEXT DEFAULT '-',
        durum           TEXT DEFAULT 'HAZIRLANIYOR',
        olusturma       TEXT DEFAULT (datetime('now','localtime'))
    )""")

    # ── STOK HAREKETLERİ ──────────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS hareket (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        hareket_tipi    TEXT NOT NULL,   -- SATIS / MAL_GIRIS / DUZELTME
        stok_id         INTEGER REFERENCES stok(id),
        birim_id        INTEGER REFERENCES stok_birimi(id),
        musteri_adi     TEXT DEFAULT '',
        adet            INTEGER DEFAULT 1,
        birim_fiyat     REAL DEFAULT 0.0,
        toplam_tutar    REAL DEFAULT 0.0,
        tedarikci       TEXT DEFAULT '',
        giris_fiyati    REAL DEFAULT 0.0,
        notlar          TEXT DEFAULT '',
        zaman           TEXT DEFAULT (datetime('now','localtime')),
        stok_sonrasi    INTEGER DEFAULT 0
    )""")

    # ── EKSİK KURALLARI ───────────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS eksik_kural (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        kategori        TEXT NOT NULL,
        marka           TEXT NOT NULL,
        min_adet        INTEGER DEFAULT 1,
        aktif           INTEGER DEFAULT 1
    )""")

    conn.commit(); conn.close()


# ── Yardımcı: yeni birim ekle (her fiziksel parça için) ───────────────────
def birim_ekle(stok_id: int, adet: int = 1) -> list:
    """
    Bir ürüne 'adet' kadar yeni fiziksel parça ekler.
    Her biri için barkod_id üretir: "{stok_id}-{sıra}"
    Oluşturulan birim id listesini döner.
    """
    conn = get_conn()
    # Mevcut max sıra numarasını bul
    mevcut = conn.execute(
        "SELECT barkod_id FROM stok_birimi WHERE stok_id=?", (stok_id,)
    ).fetchall()
    max_sira = 0
    for row in mevcut:
        try:
            sira = int(row["barkod_id"].split("-")[1])
            if sira > max_sira:
                max_sira = sira
        except: pass

    yeni_idler = []
    for i in range(1, adet + 1):
        sira     = max_sira + i
        barkod   = f"{stok_id}-{sira}"
        cursor   = conn.execute(
            "INSERT INTO stok_birimi (stok_id, barkod_id) VALUES (?,?)",
            (stok_id, barkod))
        yeni_idler.append((cursor.lastrowid, barkod))

    # stok tablosundaki stok_miktari'ni güncelle (hızlı okuma için)
    conn.execute(
        "UPDATE stok SET stok_miktari = "
        "(SELECT COUNT(*) FROM stok_birimi WHERE stok_id=? AND durum='DEPODA'), "
        "guncelleme=datetime('now','localtime') WHERE id=?",
        (stok_id, stok_id))
    conn.commit(); conn.close()
    return yeni_idler


def stok_miktari_guncelle(stok_id: int):
    """stok tablosundaki stok_miktari'ni stok_birimi sayısından hesapla."""
    conn = get_conn()
    conn.execute(
        "UPDATE stok SET stok_miktari = "
        "(SELECT COUNT(*) FROM stok_birimi WHERE stok_id=? AND durum='DEPODA'), "
        "guncelleme=datetime('now','localtime') WHERE id=?",
        (stok_id, stok_id))
    conn.commit(); conn.close()


def barkod_coz(barkod_str: str):
    """
    Barkod string'inden stok_id ve birim bilgilerini döner.
    "99-2" → {stok_id:99, birim_id:X, barkod_id:"99-2", durum:..., ...}
    Sadece sayı girilirse (eski format) → stok kaydını döner.
    """
    conn = get_conn()
    if "-" in str(barkod_str):
        row = conn.execute(
            "SELECT sb.*, s.kategori, s.marka, s.yaygin_ad, s.ref1, s.fiyat "
            "FROM stok_birimi sb JOIN stok s ON s.id=sb.stok_id "
            "WHERE sb.barkod_id=?", (barkod_str,)).fetchone()
    else:
        # Eski ID formatı — stok_id olarak yorumla
        row = conn.execute(
            "SELECT * FROM stok WHERE id=?", (int(barkod_str),)).fetchone()
    conn.close()
    return dict(row) if row else None


# ── Yardımcı fonksiyonlar ──────────────────────────────────────────────────
import pandas as pd

def v(text, default="-"):
    if pd.isna(text) if hasattr(pd, 'isna') else False: return default
    s = str(text).strip()
    return default if s.lower() in ('nan', 'none', '', 'null') else s

def to_int(val):
    try: return int(float(str(val).replace(',', '.')))
    except: return 0
