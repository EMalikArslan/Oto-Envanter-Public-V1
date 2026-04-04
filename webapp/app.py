"""
webapp/app.py  —  Flask uygulama fabrikası
Çalıştır: python webapp/app.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from flask_login import LoginManager

from webapp.config   import Config
from webapp.database import get_db, close_db, init_db

login_manager = LoginManager()

def create_app():
    app = Flask(__name__,
                template_folder="templates",
                static_folder="static")
    app.config.from_object(Config)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["LABELS_DIR"],    exist_ok=True)

    # DB
    app.teardown_appcontext(close_db)
    init_db(app)

    # Login
    login_manager.init_app(app)
    login_manager.login_view     = "auth.giris"
    login_manager.login_message  = "Lütfen giriş yapın."

    from webapp.models import Kullanici
    @login_manager.user_loader
    def load_user(user_id):
        db = get_db()
        row = db.execute("SELECT * FROM kullanici WHERE id=?", (user_id,)).fetchone()
        return Kullanici(row) if row else None

    # Blueprint'ler
    from webapp.auth.routes   import bp as auth_bp
    from webapp.admin.routes  import bp as admin_bp
    from webapp.musteri.routes import bp as musteri_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp,  url_prefix="/admin")
    app.register_blueprint(musteri_bp, url_prefix="/musteri")

    # Ana sayfa yönlendirmesi
    from flask import redirect, url_for
    from flask_login import current_user

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            if current_user.rol in ("admin", "calisan"):
                return redirect(url_for("admin.dashboard"))
            return redirect(url_for("musteri.dashboard"))
        return redirect(url_for("auth.giris"))

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)
