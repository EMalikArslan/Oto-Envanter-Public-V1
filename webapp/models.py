from flask_login import UserMixin

class Kullanici(UserMixin):
    def __init__(self, row):
        self.id       = row["id"]
        self.email    = row["email"]
        self.ad_soyad = row["ad_soyad"]
        self.telefon  = row["telefon"]
        self.rol      = row["rol"]
        self.aktif    = row["aktif"]

    def get_id(self):
        return str(self.id)

    @property
    def is_active(self):
        return bool(self.aktif)

    @property
    def is_admin(self):
        return self.rol == "admin"

    @property
    def is_calisan(self):
        return self.rol in ("admin", "calisan")
