from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, jsonify, abort)
from flask_login import login_required, current_user

from webapp.database import get_db

bp = Blueprint("musteri", __name__)

def musteri_gerekli(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.giris"))
        return f(*args, **kwargs)
    return decorated

# ── Dashboard ─────────────────────────────────────────────────────────────────
@bp.route("/")
@login_required
@musteri_gerekli
def dashboard():
    db = get_db()
    bekleyen = db.execute(
        "SELECT COUNT(*) FROM siparis WHERE musteri_id=? AND durum='beklemede'",
        (current_user.id,)).fetchone()[0]
    toplam_siparis = db.execute(
        "SELECT COUNT(*) FROM siparis WHERE musteri_id=?",
        (current_user.id,)).fetchone()[0]
    son_siparisler = db.execute("""
        SELECT s.*, COUNT(sk.id) as kalem_sayisi
        FROM siparis s LEFT JOIN siparis_kalem sk ON sk.siparis_id=s.id
        WHERE s.musteri_id=? GROUP BY s.id ORDER BY s.id DESC LIMIT 5
    """, (current_user.id,)).fetchall()
    return render_template("musteri/dashboard.html",
                           bekleyen=bekleyen,
                           toplam_siparis=toplam_siparis,
                           son_siparisler=son_siparisler)

# ── Ürünler ───────────────────────────────────────────────────────────────────
@bp.route("/urunler")
@login_required
def urunler():
    db  = get_db()
    kat = request.args.get("kat", "")
    ara = request.args.get("ara", "").strip()

    sorgu = """
        SELECT s.*, COALESCE(d.n,0) AS depoda,
               g.dosya AS kapak,
               COALESCE(i_stok.oran, i_kat.oran, 0) AS iskonto_oran
        FROM stok s
        LEFT JOIN (SELECT stok_id,COUNT(*) n FROM stok_birimi WHERE durum='DEPODA' GROUP BY stok_id) d ON d.stok_id=s.id
        LEFT JOIN (SELECT stok_id, dosya FROM urun_gorsel WHERE sira=0) g ON g.stok_id=s.id
        LEFT JOIN (SELECT stok_id, oran FROM iskonto WHERE musteri_id=? AND stok_id IS NOT NULL) i_stok ON i_stok.stok_id=s.id
        LEFT JOIN (SELECT kategori, oran FROM iskonto WHERE musteri_id=? AND stok_id IS NULL) i_kat ON i_kat.kategori=s.kategori
        WHERE d.n > 0
    """
    params = [current_user.id, current_user.id]

    if kat:
        sorgu += " AND s.kategori=?"
        params.append(kat)
    if ara:
        sorgu += " AND (s.marka LIKE ? OR s.yaygin_ad LIKE ? OR s.ref1 LIKE ? OR s.ref2 LIKE ?)"
        params += [f"%{ara}%"] * 4

    sorgu += " ORDER BY s.marka, s.yaygin_ad"
    rows = db.execute(sorgu, params).fetchall()

    kategoriler = db.execute("SELECT DISTINCT kategori FROM stok ORDER BY kategori").fetchall()
    return render_template("musteri/urunler.html", rows=rows,
                           kategoriler=kategoriler, kat=kat, ara=ara)

@bp.route("/urunler/<int:sid>")
@login_required
def urun_detay(sid):
    db   = get_db()
    stok = db.execute("""
        SELECT s.*, COALESCE(d.n,0) AS depoda,
               COALESCE(i_stok.oran, i_kat.oran, 0) AS iskonto_oran
        FROM stok s
        LEFT JOIN (SELECT stok_id,COUNT(*) n FROM stok_birimi WHERE durum='DEPODA' GROUP BY stok_id) d ON d.stok_id=s.id
        LEFT JOIN (SELECT stok_id,oran FROM iskonto WHERE musteri_id=? AND stok_id IS NOT NULL) i_stok ON i_stok.stok_id=s.id
        LEFT JOIN (SELECT kategori,oran FROM iskonto WHERE musteri_id=? AND stok_id IS NULL) i_kat ON i_kat.kategori=s.kategori
        WHERE s.id=?
    """, (current_user.id, current_user.id, sid)).fetchone()
    if not stok: abort(404)
    gorseller = db.execute("SELECT * FROM urun_gorsel WHERE stok_id=? ORDER BY sira", (sid,)).fetchall()
    return render_template("musteri/urun_detay.html", stok=stok, gorseller=gorseller)

# ── Sepet & Sipariş ───────────────────────────────────────────────────────────
@bp.route("/sepete-ekle", methods=["POST"])
@login_required
def sepete_ekle():
    stok_id = int(request.form["stok_id"])
    adet    = max(1, int(request.form.get("adet", 1)))

    if "sepet" not in __import__("flask").session:
        __import__("flask").session["sepet"] = {}
    sepet = __import__("flask").session["sepet"]
    key   = str(stok_id)
    sepet[key] = sepet.get(key, 0) + adet
    __import__("flask").session.modified = True
    flash("Sepete eklendi.", "success")
    return redirect(request.referrer or url_for("musteri.urunler"))

@bp.route("/sepet")
@login_required
def sepet():
    from flask import session
    sepet  = session.get("sepet", {})
    db     = get_db()
    kalemler = []
    toplam   = 0
    for stok_id_str, adet in sepet.items():
        row = db.execute("""
            SELECT s.*, COALESCE(d.n,0) AS depoda,
                   COALESCE(i_stok.oran, i_kat.oran, 0) AS iskonto_oran
            FROM stok s
            LEFT JOIN (SELECT stok_id,COUNT(*) n FROM stok_birimi WHERE durum='DEPODA' GROUP BY stok_id) d ON d.stok_id=s.id
            LEFT JOIN (SELECT stok_id,oran FROM iskonto WHERE musteri_id=? AND stok_id IS NOT NULL) i_stok ON i_stok.stok_id=s.id
            LEFT JOIN (SELECT kategori,oran FROM iskonto WHERE musteri_id=? AND stok_id IS NULL) i_kat ON i_kat.kategori=s.kategori
            WHERE s.id=?
        """, (current_user.id, current_user.id, int(stok_id_str))).fetchone()
        if not row: continue
        try:
            fiyat     = float(str(row["fiyat"]).replace(",","."))
            iskonto   = float(row["iskonto_oran"] or 0)
            net_fiyat = fiyat * (1 - iskonto / 100)
            satir_top = net_fiyat * adet
            toplam   += satir_top
            kalemler.append({"stok": row, "adet": adet,
                             "net_fiyat": net_fiyat, "satir_top": satir_top,
                             "iskonto": iskonto})
        except:
            kalemler.append({"stok": row, "adet": adet,
                             "net_fiyat": 0, "satir_top": 0, "iskonto": 0})
    return render_template("musteri/sepet.html", kalemler=kalemler, toplam=toplam)

@bp.route("/sepet/guncelle", methods=["POST"])
@login_required
def sepet_guncelle():
    from flask import session
    stok_id = request.form.get("stok_id")
    adet    = int(request.form.get("adet", 0))
    sepet   = session.get("sepet", {})
    if adet <= 0:
        sepet.pop(stok_id, None)
    else:
        sepet[stok_id] = adet
    session["sepet"] = sepet
    return redirect(url_for("musteri.sepet"))

@bp.route("/siparis-ver", methods=["POST"])
@login_required
def siparis_ver():
    from flask import session
    sepet = session.get("sepet", {})
    if not sepet:
        flash("Sepetiniz boş.", "warning")
        return redirect(url_for("musteri.sepet"))

    db     = get_db()
    notlar = request.form.get("notlar", "")
    toplam = 0
    kalemler = []

    for stok_id_str, adet in sepet.items():
        row = db.execute("""
            SELECT s.*,
                   COALESCE(i_stok.oran, i_kat.oran, 0) AS iskonto_oran
            FROM stok s
            LEFT JOIN (SELECT stok_id,oran FROM iskonto WHERE musteri_id=? AND stok_id IS NOT NULL) i_stok ON i_stok.stok_id=s.id
            LEFT JOIN (SELECT kategori,oran FROM iskonto WHERE musteri_id=? AND stok_id IS NULL) i_kat ON i_kat.kategori=s.kategori
            WHERE s.id=?
        """, (current_user.id, current_user.id, int(stok_id_str))).fetchone()
        if not row: continue
        try:
            fiyat     = float(str(row["fiyat"]).replace(",","."))
            iskonto   = float(row["iskonto_oran"] or 0)
            net_fiyat = fiyat * (1 - iskonto / 100)
            satir_top = net_fiyat * adet
            toplam   += satir_top
            kalemler.append((int(stok_id_str), adet, net_fiyat, iskonto, satir_top))
        except:
            pass

    cur = db.execute(
        "INSERT INTO siparis (musteri_id, toplam, notlar) VALUES (?,?,?)",
        (current_user.id, round(toplam,2), notlar)
    )
    spid = cur.lastrowid
    for stok_id, adet, bp_, isk, top in kalemler:
        db.execute(
            "INSERT INTO siparis_kalem (siparis_id,stok_id,adet,birim_fiyat,iskonto_oran,toplam) VALUES (?,?,?,?,?,?)",
            (spid, stok_id, adet, bp_, isk, top)
        )
    db.commit()
    session.pop("sepet", None)
    flash(f"✓ Siparişiniz alındı — #{spid}", "success")
    return redirect(url_for("musteri.siparis_detay", spid=spid))

# ── Siparişlerim ──────────────────────────────────────────────────────────────
@bp.route("/siparislerim")
@login_required
def siparislerim():
    db   = get_db()
    rows = db.execute("""
        SELECT s.*, COUNT(sk.id) as kalem_sayisi
        FROM siparis s LEFT JOIN siparis_kalem sk ON sk.siparis_id=s.id
        WHERE s.musteri_id=? GROUP BY s.id ORDER BY s.id DESC
    """, (current_user.id,)).fetchall()
    return render_template("musteri/siparislerim.html", rows=rows)

@bp.route("/siparislerim/<int:spid>")
@login_required
def siparis_detay(spid):
    db     = get_db()
    sipari = db.execute(
        "SELECT * FROM siparis WHERE id=? AND musteri_id=?",
        (spid, current_user.id)).fetchone()
    if not sipari: abort(404)
    kalemler = db.execute("""
        SELECT sk.*, s.marka, s.yaygin_ad, s.kategori
        FROM siparis_kalem sk JOIN stok s ON s.id=sk.stok_id
        WHERE sk.siparis_id=?
    """, (spid,)).fetchall()
    return render_template("musteri/siparis_detay.html", siparis=sipari, kalemler=kalemler)
