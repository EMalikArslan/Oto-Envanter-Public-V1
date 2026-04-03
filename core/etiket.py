import os, sys, subprocess
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime

try: import qrcode, qrcode.constants; QR_OK=True
except: QR_OK=False
try: import barcode; from barcode.writer import ImageWriter; BC_OK=True
except: BC_OK=False

def _base():
    return os.path.dirname(sys.executable) if getattr(sys,"frozen",False) else \
           os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BASE       = _base()
LOGO_PATH  = os.path.join(BASE,"assets","logo.png")
LABELS_DIR = os.path.join(BASE,"labels")
WP_LINK    = "https://wa.me/message/MNGBLXCP7E77E1"

TR_MAP = str.maketrans("ğĞışİöÖüÜçÇ","gGisiOoUuCc")
def _tr(s): return str(s or "").translate(TR_MAP)

def _font_bul(kalin=True):
    k=["C:/Windows/Fonts/arialbd.ttf","C:/Windows/Fonts/calibrib.ttf",
       "C:/Windows/Fonts/verdanab.ttf",
       "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
       "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
    n=["C:/Windows/Fonts/arial.ttf","C:/Windows/Fonts/calibri.ttf",
       "C:/Windows/Fonts/verdana.ttf",
       "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
       "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    for p in (k if kalin else n):
        if os.path.exists(p): return p
    return None

def _f(yol, pt):
    if yol:
        try: return ImageFont.truetype(yol, pt)
        except: pass
    return ImageFont.load_default()


def etiket_olustur(barkod_id, stok_id, kategori, marka, ad, secili_refler):
    """40x30mm @ 300dpi yatay — büyük font, Türkçe uyumlu."""
    os.makedirs(LABELS_DIR, exist_ok=True)
    W, H = 472, 354   # 40x30 mm @ 300 dpi
    PAD  = 10
    img  = Image.new("RGB",(W,H),"white")
    draw = ImageDraw.Draw(img)
    fp_k = _font_bul(True); fp_n = _font_bul(False)

    f_marka = _f(fp_k, 30)
    f_model = _f(fp_n, 22)
    f_ref   = _f(fp_n, 20)
    f_id    = _f(fp_k, 17)
    f_kucuk = _f(fp_n, 13)

    # ── Logo (sol üst) ────────────────────────────────────────────────────
    logo_w = 0
    if os.path.exists(LOGO_PATH):
        try:
            logo = Image.open(LOGO_PATH).convert("RGBA")
            lh   = min(46, H // 7)
            lw   = int(logo.size[0] * lh / logo.size[1])
            lw   = min(lw, 110)
            logo = logo.resize((lw, lh), Image.Resampling.LANCZOS)
            patch= Image.new("RGB", logo.size, "white")
            patch.paste(logo, mask=logo.split()[3])
            img.paste(patch, (PAD, PAD))
            logo_w = lw + PAD
        except:
            pass
    if not logo_w:
        draw.text((PAD, PAD+6), "ARES", fill="#C0392B", font=f_kucuk)
        logo_w = 48

    # ── Kırmızı dikey çubuk ───────────────────────────────────────────────
    bant_x = logo_w + PAD
    draw.rectangle([(bant_x, PAD), (bant_x+5, PAD+72)], fill="#C0392B")

    # ── Marka & Model ─────────────────────────────────────────────────────
    tx = bant_x + 10
    draw.text((tx, PAD),      _tr(marka)[:20], fill="#1A1917", font=f_marka)
    draw.text((tx, PAD + 34), _tr(ad)[:26],    fill="#555555", font=f_model)

    # ── Ayırıcı ───────────────────────────────────────────────────────────
    sep_y = PAD + 80
    draw.line([(PAD, sep_y), (W-PAD, sep_y)], fill="#CCCCCC", width=1)
    sep_y += 6

    # ── Referanslar ───────────────────────────────────────────────────────
    y = sep_y
    for ref in secili_refler[:3]:
        if ref and ref != "-":
            draw.text((PAD+4, y), f"- {_tr(str(ref))[:32]}", fill="#1A1917", font=f_ref)
            y += 24

    # ── Alt alan ──────────────────────────────────────────────────────────
    alt_y = H - 88
    draw.line([(PAD, alt_y), (W-PAD, alt_y)], fill="#CCCCCC", width=1)
    alt_y += 4

    # QR (sağ alt)
    qr_size = 60; qr_x = W - PAD - qr_size
    if QR_OK:
        try:
            qr = qrcode.QRCode(box_size=2, border=1,
                               error_correction=qrcode.constants.ERROR_CORRECT_L)
            qr.add_data(WP_LINK); qr.make(fit=True)
            qi = qr.make_image().resize((qr_size, qr_size), Image.Resampling.LANCZOS)
            img.paste(qi, (qr_x, alt_y + 2))
        except:
            pass

    # ID
    draw.text((PAD, alt_y + 4), f"ID: {barkod_id}", fill="#1A1917", font=f_id)

    # Barkod (sol alt, QR'ın soluna kadar)
    if BC_OK:
        bc_w = qr_x - PAD - 6
        bc_h = H - (alt_y + 26) - PAD
        try:
            tmp = os.path.join(LABELS_DIR, f"_t_{str(barkod_id).replace('-','_')}")
            barcode.get_barcode_class("code128")(str(barkod_id), writer=ImageWriter()).save(
                tmp, {"write_text": False, "module_height": 10, "quiet_zone": 1})
            bi = Image.open(tmp + ".png").resize((bc_w, max(bc_h, 30)),
                                                 Image.Resampling.LANCZOS)
            img.paste(bi, (PAD, alt_y + 26))
            try: os.remove(tmp + ".png")
            except: pass
        except:
            pass

    safe = str(barkod_id).replace("-", "_")
    path = os.path.join(LABELS_DIR, f"e_{safe}.png")
    img.save(path)
    return path


def yazici_gonder(dosya_yolu, yazici_adi=None):
    if not os.path.exists(dosya_yolu): return False,"Dosya yok"
    try:
        if sys.platform=="win32": os.startfile(dosya_yolu,"print"); return True,"OK"
        cmd=["lp"]+(["-d",yazici_adi] if yazici_adi else [])+["-o","fit-to-page",dosya_yolu]
        r=subprocess.run(cmd,capture_output=True,text=True,timeout=10)
        return (True,"OK") if r.returncode==0 else (False,r.stderr.strip())
    except Exception as e: return False,str(e)

def yazici_listesi():
    try:
        if sys.platform=="win32":
            import win32print; return [p[2] for p in win32print.EnumPrinters(2)]
        r=subprocess.run(["lpstat","-p"],capture_output=True,text=True,timeout=5)
        return [l.split()[1] for l in r.stdout.splitlines() if l.startswith("printer ")]
    except: return []
