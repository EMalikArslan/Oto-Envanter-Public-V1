"""
webapp/database.py
Mevcut core/database.py'yi sarar + web'e özgü tablolar (kullanıcı, sipariş, iskonto) ekler.
"""
import sqlite3, os
from flask import g, current_app
from werkzeug.security import generate_password_hash

# ── Bağlantı ──────────────────────────────────────────────────────────────────

def get_db():
    if "db" not in g:
        db = sqlite3.connect(
            current_app.config["DATABASE"],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA foreign_keys=ON")
        g.db = db
    return g.db

def close_db(e=None):
    db = g.pop("db", None)
    if db:
        db.close()

# ── Şema ──────────────────────────────────────────────────────────────────────

SCHEMA_WEB = """
-- Kullanıcılar (admin / calisan / musteri)
CREATE TABLE IF NOT EXISTS kullanici (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT    UNIQUE NOT NULL,
    sifre_hash    TEXT    NOT NULL,
    ad_soyad      TEXT    NOT NULL,
    telefon       TEXT    DEFAULT '',
    rol           TEXT    NOT NULL DEFAULT 'musteri',   -- admin|calisan|musteri
    aktif         INTEGER NOT NULL DEFAULT 0,           -- 0=beklemede, 1=aktif
    olusturma     TEXT    DEFAULT (datetime('now','localtime')),
    son_giris     TEXT
);

-- Ürün görselleri (bir ürüne birden fazla resim)
CREATE TABLE IF NOT EXISTS urun_gorsel (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    stok_id   INTEGER NOT NULL REFERENCES stok(id) ON DELETE CASCADE,
    dosya     TEXT    NOT NULL,
    sira      INTEGER DEFAULT 0,
    olusturma TEXT    DEFAULT (datetime('now','localtime'))
);

-- Müşteriye özel iskonto (kategori veya ürün bazlı)
CREATE TABLE IF NOT EXISTS iskonto (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    musteri_id  INTEGER NOT NULL REFERENCES kullanici(id) ON DELETE CASCADE,
    stok_id     INTEGER REFERENCES stok(id) ON DELETE CASCADE,
    kategori    TEXT,
    oran        REAL    NOT NULL DEFAULT 0,   -- % olarak (örn: 15 = %15)
    olusturma   TEXT    DEFAULT (datetime('now','localtime')),
    CHECK (stok_id IS NOT NULL OR kategori IS NOT NULL)
);

-- Siparişler
CREATE TABLE IF NOT EXISTS siparis (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    musteri_id  INTEGER NOT NULL REFERENCES kullanici(id),
    durum       TEXT    NOT NULL DEFAULT 'beklemede',  -- beklemede|onaylandi|hazirlaniyor|kargolandi|iptal
    toplam      REAL    DEFAULT 0,
    notlar      TEXT    DEFAULT '',
    olusturma   TEXT    DEFAULT (datetime('now','localtime')),
    guncelleme  TEXT    DEFAULT (datetime('now','localtime'))
);

-- Sipariş kalemleri
CREATE TABLE IF NOT EXISTS siparis_kalem (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    siparis_id  INTEGER NOT NULL REFERENCES siparis(id) ON DELETE CASCADE,
    stok_id     INTEGER NOT NULL REFERENCES stok(id),
    adet        INTEGER NOT NULL DEFAULT 1,
    birim_fiyat REAL    NOT NULL,
    iskonto_oran REAL   DEFAULT 0,
    toplam      REAL    NOT NULL
);
"""

def init_db(app):
    """Uygulama başlarken tabloları oluştur, admin yoksa oluştur."""
    with app.app_context():
        db = get_db()
        db.executescript(SCHEMA_WEB)
        db.commit()
        _ilk_admin_olustur(db)

def _ilk_admin_olustur(db):
    mevcut = db.execute("SELECT id FROM kullanici WHERE rol='admin' LIMIT 1").fetchone()
    if not mevcut:
        db.execute(
            "INSERT INTO kullanici (email, sifre_hash, ad_soyad, rol, aktif) VALUES (?,?,?,?,?)",
            ("admin@ares.com",
             generate_password_hash("admin123"),
             "Sistem Admini", "admin", 1)
        )
        db.commit()
        print("✓ İlk admin oluşturuldu → admin@ares.com / admin123")
