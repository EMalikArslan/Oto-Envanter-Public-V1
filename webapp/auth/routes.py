from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash

from webapp.database import get_db
from webapp.models   import Kullanici

bp = Blueprint("auth", __name__)


@bp.route("/giris", methods=["GET", "POST"])
def giris():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        sifre = request.form.get("sifre", "")
        db    = get_db()
        row   = db.execute("SELECT * FROM kullanici WHERE email=?", (email,)).fetchone()

        if not row or not check_password_hash(row["sifre_hash"], sifre):
            flash("E-posta veya şifre hatalı.", "danger")
            return render_template("auth/giris.html")

        if not row["aktif"]:
            flash("Hesabınız henüz onaylanmadı. Yönetici onayını bekleyin.", "warning")
            return render_template("auth/giris.html")

        kullanici = Kullanici(row)
        login_user(kullanici, remember=True)
        db.execute("UPDATE kullanici SET son_giris=datetime('now','localtime') WHERE id=?",
                   (kullanici.id,))
        db.commit()

        nxt = request.args.get("next")
        if nxt and nxt.startswith("/"):
            return redirect(nxt)
        if kullanici.is_calisan:
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("musteri.dashboard"))

    return render_template("auth/giris.html")


@bp.route("/kayit", methods=["GET", "POST"])
def kayit():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        sifre    = request.form.get("sifre", "")
        sifre2   = request.form.get("sifre2", "")
        ad_soyad = request.form.get("ad_soyad", "").strip()
        telefon  = request.form.get("telefon", "").strip()
        db       = get_db()

        if not email or not sifre or not ad_soyad:
            flash("Tüm zorunlu alanları doldurun.", "danger")
        elif sifre != sifre2:
            flash("Şifreler eşleşmiyor.", "danger")
        elif len(sifre) < 6:
            flash("Şifre en az 6 karakter olmalı.", "danger")
        elif db.execute("SELECT id FROM kullanici WHERE email=?", (email,)).fetchone():
            flash("Bu e-posta zaten kayıtlı.", "danger")
        else:
            db.execute(
                "INSERT INTO kullanici (email, sifre_hash, ad_soyad, telefon, rol, aktif) "
                "VALUES (?,?,?,?,'musteri',0)",
                (email, generate_password_hash(sifre), ad_soyad, telefon)
            )
            db.commit()
            flash("Kaydınız alındı. Yönetici onayından sonra giriş yapabilirsiniz.", "success")
            return redirect(url_for("auth.giris"))

    return render_template("auth/kayit.html")


@bp.route("/cikis")
@login_required
def cikis():
    logout_user()
    flash("Çıkış yapıldı.", "info")
    return redirect(url_for("auth.giris"))
