import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class Config:
    SECRET_KEY          = os.environ.get("SECRET_KEY", "ares-gizli-anahtar-2024-degistir")
    DATABASE            = os.path.join(BASE_DIR, "ares.db")
    UPLOAD_FOLDER       = os.path.join(BASE_DIR, "webapp", "static", "img", "urunler")
    LABELS_DIR          = os.path.join(BASE_DIR, "labels")
    MAX_CONTENT_LENGTH  = 8 * 1024 * 1024   # 8 MB max resim
    ALLOWED_EXTENSIONS  = {"png", "jpg", "jpeg", "webp"}
    ITEMS_PER_PAGE      = 50
