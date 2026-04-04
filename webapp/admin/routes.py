import os, sys
from flask import (Blueprint, render_template, redirect, url_for, flash,
                   request, jsonify, send_file, current_app, abort)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash

from webapp.database import get_db

bp = Blueprint("admin", __name__)

# ── Decorator: sadece çalışan/admin ──────────────────────────────────────────
def calisan_gerekli(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_calisan:
            abort(403)
        return f(*args, **kwargs)
    return login_required(decorated)

def admin_gerekli(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return login_required(decorated)

# ── Dashboard ──────────────────────────────────────────────────────────────
@bp.route("/")
@calisan_gerekli
def dashboard():
    db = get_db()
    ozet = {
        "toplam_urun":  db.execute("SELECT COUNT(*) FROM stok").fetchone()[0],
        "depoda":       db.execute("SELECT COUNT(*) FROM stok_birimi WHERE durum='DEPODA'").fetchone()[0],
        "turda":        db.execute("SELECT COUNT(*) FROM stok_birimi WHERE durum='TURDA'").fetchone()[0],
        "satildi":      db.execute("SELECT COUNT(*) FROM stok_birimi WHERE durum='SATILDI'").fetchone()[0],
        "bekl_siparis": db.execute("SELECT COUNT(*) FROM siparis WHERE durum='beklemede'").fetchone()[0],
        "bekl_kayit":   db.execute("SELECT COUNT(*) FROM kullanici WHERE aktif=0 AND rol='musteri'").fetchone()[0],
        "toplam_kargo": db.execute("SELECT COUNT(*) FROM kargo").fetchone()[0] if _tablo_var(db,"kargo") else 0,
    }
    son_hareketler = db.execute("""
        SELECT h.*, s.marka, s.yaygin_ad
        FROM hareket h JOIN stok s ON s.id=h.stok_id
        ORDER BY h.id DESC LIMIT 10
    """).fetchall() if _tablo_var(db,"hareket") else []

    return render_template("admin/dashboard.html", ozet=ozet, son_hareketler=son_hareketler)

def _tablo_var(db, tablo):
    return db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tablo,)
    ).fetchone() is not None

# ── STOK ──────────────────────────────────────────────────────────────────────
@bp.route("/stok")
@calisan_gerekli
def stok():
    db  = get_db()
    kat = request.args.get("kat", "Beyin")
    rows = db.execute("""
        SELECT s.*,
            COALESCE(d.n,0) AS depoda,
            COALESCE(t.n,0) AS turda,
            COALESCE(e.n,0) AS etiket_bekl,
            g.dosya         AS kapak
        FROM stok s
        LEFT JOIN (SELECT stok_id,COUNT(*) n FROM stok_birimi WHERE durum='DEPODA' GROUP BY stok_id) d ON d.stok_id=s.id
        LEFT JOIN (SELECT stok_id,COUNT(*) n FROM stok_birimi WHERE durum='TURDA'  GROUP BY stok_id) t ON t.stok_id=s.id
        LEFT JOIN (SELECT stok_id,COUNT(*) n FROM stok_birimi WHERE durum='DEPODA' AND etiket_basildi='HAYIR' GROUP BY stok_id) e ON e.stok_id=s.id
        LEFT JOIN (SELECT stok_id, dosya FROM urun_gorsel WHERE sira=0) g ON g.stok_id=s.id
        WHERE s.kategori=?
        ORDER BY CAST(s.id AS INTEGER)
    """, (kat,)).fetchall()
    toplam_depoda = sum(r["depoda"] for r in rows)
    toplam_turda  = sum(r["turda"]  for r in rows)
    return render_template("admin/stok.html", rows=rows, kat=kat,
                           toplam_depoda=toplam_depoda, toplam_turda=toplam_turda)

@bp.route("/stok/ekle", methods=["GET","POST"])
@calisan_gerekli
def stok_ekle():
    db = get_db()
    if request.method == "POST":
        f = request.form
        adet = int(f.get("adet",1) or 1)
        cur  = db.execute("""
            INSERT INTO stok (kategori,marka,yaygin_ad,motor,ref1,ref2,ref3,ref4,ref5,fiyat,stok_miktari)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (f["kategori"], f["marka"], f.get("yaygin_ad",""), f.get("motor",""),
              f.get("ref1","-"), f.get("ref2","-"), f.get("ref3","-"),
              f.get("ref4","-"), f.get("ref5","-"), f.get("fiyat",""), adet))
        sid = cur.lastrowid
        for i in range(1, adet+1):
            db.execute("INSERT INTO stok_birimi (stok_id, barkod_id) VALUES (?,?)",
                       (sid, f"{sid}-{i}"))
        db.commit()
        _gorsel_yukle(request.files.getlist("gorseller"), sid, db)
        flash(f"✓ Ürün eklendi — ID:{sid}, {adet} birim", "success")
        return redirect(url_for("admin.stok", kat=f["kategori"]))
    return render_template("admin/stok_form.html", kayit=None)

@bp.route("/stok/<int:sid>/duzenle", methods=["GET","POST"])
@calisan_gerekli
def stok_duzenle(sid):
    db    = get_db()
    kayit = db.execute("SELECT * FROM stok WHERE id=?", (sid,)).fetchone()
    if not kayit: abort(404)

    if request.method == "POST":
        f    = request.form
        ekle = int(f.get("birim_ekle",0) or 0)
        cika = int(f.get("birim_cikar",0) or 0)
        db.execute("""
            UPDATE stok SET kategori=?,marka=?,yaygin_ad=?,motor=?,
            ref1=?,ref2=?,ref3=?,ref4=?,ref5=?,fiyat=?,
            guncelleme=datetime('now','localtime') WHERE id=?
        """, (f["kategori"], f["marka"], f.get("yaygin_ad",""), f.get("motor",""),
              f.get("ref1","-"), f.get("ref2","-"), f.get("ref3","-"),
              f.get("ref4","-"), f.get("ref5","-"), f.get("fiyat",""), sid))
        if ekle > 0:
            mevcut = db.execute("SELECT MAX(CAST(SUBSTR(barkod_id,INSTR(barkod_id,'-')+1) AS INT)) FROM stok_birimi WHERE stok_id=?", (sid,)).fetchone()[0] or 0
            for i in range(1, ekle+1):
                db.execute("INSERT INTO stok_birimi (stok_id,barkod_id) VALUES (?,?)",
                           (sid, f"{sid}-{mevcut+i}"))
        if cika > 0:
            for b in db.execute("SELECT id FROM stok_birimi WHERE stok_id=? AND durum='DEPODA' LIMIT ?", (sid, cika)).fetchall():
                db.execute("UPDATE stok_birimi SET durum='SATILDI' WHERE id=?", (b[0],))
        db.commit()
        _gorsel_yukle(request.files.getlist("gorseller"), sid, db)
        flash("✓ Ürün güncellendi.", "success")
        return redirect(url_for("admin.stok", kat=f["kategori"]))

    gorseller = db.execute("SELECT * FROM urun_gorsel WHERE stok_id=? ORDER BY sira", (sid,)).fetchall()
    birimler  = db.execute("SELECT * FROM stok_birimi WHERE stok_id=? ORDER BY id", (sid,)).fetchall()
    return render_template("admin/stok_form.html", kayit=dict(kayit),
                           gorseller=gorseller, birimler=birimler)

@bp.route("/stok/<int:sid>/sil", methods=["POST"])
@calisan_gerekli
def stok_sil(sid):
    db = get_db()
    db.execute("DELETE FROM stok_birimi WHERE stok_id=?", (sid,))
    db.execute("DELETE FROM urun_gorsel WHERE stok_id=?", (sid,))
    db.execute("DELETE FROM stok WHERE id=?", (sid,))
    db.commit()
    flash("Ürün silindi.", "warning")
    return redirect(request.referrer or url_for("admin.stok"))

@bp.route("/stok/<int:sid>/etiket")
@calisan_gerekli
def stok_etiket(sid):
    db   = get_db()
    stok = db.execute("SELECT * FROM stok WHERE id=?", (sid,)).fetchone()
    if not stok: abort(404)
    birimler = db.execute(
        "SELECT * FROM stok_birimi WHERE stok_id=? AND etiket_basildi='HAYIR' AND durum='DEPODA'",
        (sid,)).fetchall()
    if not birimler:
        flash("Etiketlenecek birim bulunamadı.", "info")
        return redirect(request.referrer or url_for("admin.stok"))
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from core.etiket import etiket_olustur
    refs = [stok["ref1"],stok["ref2"],stok["ref3"],stok["ref4"],stok["ref5"]]
    refs = [r for r in refs if r and r != "-"]
    yollar = []
    for b in birimler:
        try:
            yol = etiket_olustur(b["barkod_id"], sid, stok["kategori"],
                                  stok["marka"], stok["yaygin_ad"], refs)
            db.execute("UPDATE stok_birimi SET etiket_basildi='EVET' WHERE id=?", (b["id"],))
            yollar.append(yol)
        except Exception as e:
            flash(f"Hata ({b['barkod_id']}): {e}", "danger")
    db.commit()
    if yollar:
        flash(f"✓ {len(yollar)} etiket oluşturuldu. İndir:", "success")
        return redirect(url_for("admin.etiket_indir", dosya=os.path.basename(yollar[-1])))
    return redirect(request.referrer or url_for("admin.stok"))

@bp.route("/etiket/<dosya>")
@calisan_gerekli
def etiket_indir(dosya):
    yol = os.path.join(current_app.config["LABELS_DIR"], secure_filename(dosya))
    if not os.path.exists(yol): abort(404)
    return send_file(yol, mimetype="image/png", as_attachment=False)

def _gorsel_yukle(files, stok_id, db):
    upload = current_app.config["UPLOAD_FOLDER"]
    izinli = current_app.config["ALLOWED_EXTENSIONS"]
    sira   = db.execute("SELECT COALESCE(MAX(sira),0)+1 FROM urun_gorsel WHERE stok_id=?", (stok_id,)).fetchone()[0]
    for f in files:
        if not f or not f.filename: continue
        ext = f.filename.rsplit(".",1)[-1].lower()
        if ext not in izinli: continue
        dosya = f"{stok_id}_{sira}_{secure_filename(f.filename)}"
        f.save(os.path.join(upload, dosya))
        db.execute("INSERT INTO urun_gorsel (stok_id, dosya, sira) VALUES (?,?,?)",
                   (stok_id, dosya, sira))
        sira += 1
    db.commit()

@bp.route("/gorsel/<int:gid>/sil", methods=["POST"])
@calisan_gerekli
def gorsel_sil(gid):
    db  = get_db()
    row = db.execute("SELECT * FROM urun_gorsel WHERE id=?", (gid,)).fetchone()
    if row:
        try: os.remove(os.path.join(current_app.config["UPLOAD_FOLDER"], row["dosya"]))
        except: pass
        db.execute("DELETE FROM urun_gorsel WHERE id=?", (gid,))
        db.commit()
    return jsonify(ok=True)

# ── KARGO ─────────────────────────────────────────────────────────────────────
@bp.route("/kargo")
@calisan_gerekli
def kargo():
    db   = get_db()
    if not _tablo_var(db, "kargo"):
        flash("Kargo tablosu bulunamadı.", "warning")
        return render_template("admin/kargo.html", rows=[])
    rows = db.execute("""
        SELECT k.*, m.ad_soyad as musteri_adi
        FROM kargo k
        LEFT JOIN kullanici m ON m.id=k.musteri_id
        ORDER BY k.id DESC LIMIT 200
    """).fetchall()
    musteriler = db.execute("SELECT id, ad_soyad FROM kullanici WHERE rol='musteri' AND aktif=1 ORDER BY ad_soyad").fetchall()
    return render_template("admin/kargo.html", rows=rows, musteriler=musteriler)

@bp.route("/kargo/ekle", methods=["POST"])
@calisan_gerekli
def kargo_ekle():
    db = get_db()
    f  = request.form
    cur = db.execute("""
        INSERT INTO kargo (musteri_id, alici_adi, alici_adres, alici_telefon, icerik, durum)
        VALUES (?,?,?,?,?,'hazirlaniyor')
    """, (f.get("musteri_id") or None, f["alici_adi"], f.get("alici_adres",""),
          f.get("alici_telefon",""), f.get("icerik","")))
    kid = cur.lastrowid
    db.commit()
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from modules.kargo import kargo_etiketi_olustur
    try:
        row = db.execute("SELECT * FROM kargo WHERE id=?", (kid,)).fetchone()
        yol = kargo_etiketi_olustur(kid, row["alici_adi"], row["alici_adres"],
                                     row["alici_telefon"], row["icerik"])
        flash(f"✓ Kargo oluşturuldu — K{kid:06d}", "success")
        return redirect(url_for("admin.etiket_indir", dosya=os.path.basename(yol)))
    except Exception as e:
        flash(f"Kargo oluşturuldu ama etiket hatası: {e}", "warning")
    return redirect(url_for("admin.kargo"))

# ── HAREKETLER ────────────────────────────────────────────────────────────────
@bp.route("/hareketler")
@calisan_gerekli
def hareketler():
    db   = get_db()
    if not _tablo_var(db, "hareket"):
        return render_template("admin/hareketler.html", rows=[])
    rows = db.execute("""
        SELECT h.*, s.marka, s.yaygin_ad, s.kategori
        FROM hareket h JOIN stok s ON s.id=h.stok_id
        ORDER BY h.id DESC LIMIT 300
    """).fetchall()
    return render_template("admin/hareketler.html", rows=rows)

# ── TURLAR ────────────────────────────────────────────────────────────────────
@bp.route("/turlar")
@calisan_gerekli
def turlar():
    db   = get_db()
    if not _tablo_var(db, "tur"):
        return render_template("admin/turlar.html", rows=[])
    rows = db.execute("SELECT * FROM tur ORDER BY id DESC LIMIT 100").fetchall()
    return render_template("admin/turlar.html", rows=rows)

# ── MÜŞTERİLER ───────────────────────────────────────────────────────────────
@bp.route("/musteriler")
@calisan_gerekli
def musteriler():
    db   = get_db()
    rows = db.execute(
        "SELECT * FROM kullanici WHERE rol='musteri' ORDER BY olusturma DESC"
    ).fetchall()
    return render_template("admin/musteriler.html", rows=rows)

@bp.route("/musteriler/<int:mid>/onayla", methods=["POST"])
@calisan_gerekli
def musteri_onayla(mid):
    db = get_db()
    db.execute("UPDATE kullanici SET aktif=1 WHERE id=?", (mid,))
    db.commit()
    flash("Kullanıcı onaylandı.", "success")
    return redirect(url_for("admin.musteriler"))

@bp.route("/musteriler/<int:mid>/reddet", methods=["POST"])
@calisan_gerekli
def musteri_reddet(mid):
    db = get_db()
    db.execute("DELETE FROM kullanici WHERE id=? AND rol='musteri'", (mid,))
    db.commit()
    flash("Kullanıcı silindi.", "warning")
    return redirect(url_for("admin.musteriler"))

@bp.route("/musteriler/<int:mid>/iskonto", methods=["GET","POST"])
@calisan_gerekli
def musteri_iskonto(mid):
    db  = get_db()
    kul = db.execute("SELECT * FROM kullanici WHERE id=?", (mid,)).fetchone()
    if not kul: abort(404)

    if request.method == "POST":
        f = request.form
        action = f.get("action")
        if action == "ekle":
            db.execute(
                "INSERT INTO iskonto (musteri_id, stok_id, kategori, oran) VALUES (?,?,?,?)",
                (mid, f.get("stok_id") or None,
                 f.get("kategori") or None, float(f.get("oran",0)))
            )
            db.commit()
            flash("İskonto eklendi.", "success")
        elif action == "sil":
            db.execute("DELETE FROM iskonto WHERE id=? AND musteri_id=?",
                       (f["iskonto_id"], mid))
            db.commit()
            flash("İskonto silindi.", "warning")
        return redirect(url_for("admin.musteri_iskonto", mid=mid))

    iskontolar = db.execute("""
        SELECT i.*, s.marka, s.yaygin_ad FROM iskonto i
        LEFT JOIN stok s ON s.id=i.stok_id
        WHERE i.musteri_id=? ORDER BY i.id
    """, (mid,)).fetchall()
    urunler = db.execute("SELECT id, marka, yaygin_ad FROM stok ORDER BY marka").fetchall()
    return render_template("admin/iskonto.html", kul=kul,
                           iskontolar=iskontolar, urunler=urunler)

# ── SİPARİŞLER ───────────────────────────────────────────────────────────────
@bp.route("/siparisler")
@calisan_gerekli
def siparisler():
    db   = get_db()
    rows = db.execute("""
        SELECT s.*, k.ad_soyad, k.email,
               COUNT(sk.id) as kalem_sayisi
        FROM siparis s
        JOIN kullanici k ON k.id=s.musteri_id
        LEFT JOIN siparis_kalem sk ON sk.siparis_id=s.id
        GROUP BY s.id ORDER BY s.id DESC
    """).fetchall()
    return render_template("admin/siparisler.html", rows=rows)

@bp.route("/siparisler/<int:spid>")
@calisan_gerekli
def siparis_detay(spid):
    db     = get_db()
    sipari = db.execute("""
        SELECT s.*, k.ad_soyad, k.email, k.telefon
        FROM siparis s JOIN kullanici k ON k.id=s.musteri_id
        WHERE s.id=?
    """, (spid,)).fetchone()
    if not sipari: abort(404)
    kalemler = db.execute("""
        SELECT sk.*, s.marka, s.yaygin_ad, s.kategori
        FROM siparis_kalem sk JOIN stok s ON s.id=sk.stok_id
        WHERE sk.siparis_id=?
    """, (spid,)).fetchall()
    return render_template("admin/siparis_detay.html", siparis=sipari, kalemler=kalemler)

@bp.route("/siparisler/<int:spid>/durum", methods=["POST"])
@calisan_gerekli
def siparis_durum(spid):
    db    = get_db()
    durum = request.form.get("durum")
    db.execute("UPDATE siparis SET durum=?, guncelleme=datetime('now','localtime') WHERE id=?",
               (durum, spid))
    db.commit()
    flash(f"Sipariş durumu: {durum}", "success")
    return redirect(url_for("admin.siparis_detay", spid=spid))

# ── KULLANICILAR (admin only) ─────────────────────────────────────────────────
@bp.route("/kullanicilar")
@admin_gerekli
def kullanicilar():
    db   = get_db()
    rows = db.execute("SELECT * FROM kullanici ORDER BY olusturma DESC").fetchall()
    return render_template("admin/kullanicilar.html", rows=rows)

@bp.route("/kullanicilar/ekle", methods=["POST"])
@admin_gerekli
def kullanici_ekle():
    db = get_db()
    f  = request.form
    if db.execute("SELECT id FROM kullanici WHERE email=?", (f["email"],)).fetchone():
        flash("Bu e-posta zaten kayıtlı.", "danger")
        return redirect(url_for("admin.kullanicilar"))
    db.execute(
        "INSERT INTO kullanici (email,sifre_hash,ad_soyad,telefon,rol,aktif) VALUES (?,?,?,?,?,1)",
        (f["email"].lower(), generate_password_hash(f["sifre"]),
         f["ad_soyad"], f.get("telefon",""), f["rol"])
    )
    db.commit()
    flash(f"✓ Kullanıcı eklendi: {f['email']}", "success")
    return redirect(url_for("admin.kullanicilar"))

@bp.route("/kullanicilar/<int:kid>/toggle", methods=["POST"])
@admin_gerekli
def kullanici_toggle(kid):
    if kid == current_user.id:
        flash("Kendinizi devre dışı bırakamazsınız.", "danger")
        return redirect(url_for("admin.kullanicilar"))
    db  = get_db()
    row = db.execute("SELECT aktif FROM kullanici WHERE id=?", (kid,)).fetchone()
    db.execute("UPDATE kullanici SET aktif=? WHERE id=?", (0 if row["aktif"] else 1, kid))
    db.commit()
    flash("Kullanıcı durumu güncellendi.", "success")
    return redirect(url_for("admin.kullanicilar"))

# ── AYARLAR ───────────────────────────────────────────────────────────────────
@bp.route("/ayarlar", methods=["GET","POST"])
@admin_gerekli
def ayarlar():
    import json
    CONFIG_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "assets", "sheets_config.json"
    )
    if request.method == "POST":
        url = request.form.get("sheet_url","").strip()
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH,"w") as fh:
            json.dump({"sheet_url": url}, fh)
        flash("Sheets ayarları kaydedildi.", "success")
        return redirect(url_for("admin.ayarlar"))
    sheet_url = ""
    if os.path.exists(CONFIG_PATH):
        try: sheet_url = json.load(open(CONFIG_PATH)).get("sheet_url","")
        except: pass
    return render_template("admin/ayarlar.html", sheet_url=sheet_url)

# ── Sheets manuel sync ────────────────────────────────────────────────────────
@bp.route("/sheets-sync", methods=["POST"])
@calisan_gerekli
def sheets_sync():
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from core.sheets import get_sheets
    db   = get_db()
    rows = db.execute("""
        SELECT s.id,s.kategori,s.marka,s.yaygin_ad,s.motor,
               s.ref1,s.ref2,s.ref3,s.ref4,s.ref5,s.fiyat,
               COALESCE(d.n,0),COALESCE(t.n,0),s.guncelleme
        FROM stok s
        LEFT JOIN (SELECT stok_id,COUNT(*) n FROM stok_birimi WHERE durum='DEPODA' GROUP BY stok_id) d ON d.stok_id=s.id
        LEFT JOIN (SELECT stok_id,COUNT(*) n FROM stok_birimi WHERE durum='TURDA'  GROUP BY stok_id) t ON t.stok_id=s.id
    """).fetchall()
    get_sheets().stok_genel_yenile([list(r) for r in rows])
    flash(f"Sheets'e {len(rows)} ürün gönderildi.", "success")
    return redirect(request.referrer or url_for("admin.dashboard"))
