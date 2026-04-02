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
    """30x40mm @ 300dpi — TÜR YOK, büyük font, Türkçe uyumlu."""
    os.makedirs(LABELS_DIR, exist_ok=True)
    W, H = 354, 472
    PAD  = 12
    img  = Image.new("RGB",(W,H),"white")
    draw = ImageDraw.Draw(img)
    fp_k = _font_bul(True); fp_n = _font_bul(False)

    f_marka = _f(fp_k, 32)
    f_model = _f(fp_n, 26)
    f_ref   = _f(fp_n, 22)
    f_id    = _f(fp_k, 18)
    f_kucuk = _f(fp_n, 14)

    y = PAD

    # Logo
    if os.path.exists(LOGO_PATH):
        try:
            logo=Image.open(LOGO_PATH).convert("RGBA")
            bw=min(130,W-PAD*2); lh=int(logo.size[1]*bw/logo.size[0])
            logo=logo.resize((bw,lh),Image.Resampling.LANCZOS)
            patch=Image.new("RGB",logo.size,"white"); patch.paste(logo,mask=logo.split()[3])
            img.paste(patch,((W-bw)//2,y)); y+=lh+6
        except: y+=20
    else:
        draw.text((W//2,y+10),"ARES",fill="#C0392B",font=f_kucuk,anchor="mm"); y+=22

    draw.line([(PAD,y),(W-PAD,y)],fill="#DDDDDD",width=1); y+=6

    # Kırmızı çubuk
    draw.rectangle([(PAD,y),(PAD+5,y+70)],fill="#C0392B")

    # Marka
    draw.text((PAD+10,y),_tr(marka)[:22],fill="#1A1917",font=f_marka); y+=36
    # Model
    draw.text((PAD+10,y),_tr(ad)[:26],fill="#555555",font=f_model); y+=30

    draw.line([(PAD,y),(W-PAD,y)],fill="#CCCCCC",width=1); y+=7

    # Referanslar
    max_ref = max(1, min(3,(H-y-105)//26))
    for ref in secili_refler[:max_ref]:
        if ref and ref!="-":
            draw.text((PAD+6,y),f"- {_tr(str(ref))[:26]}",fill="#1A1917",font=f_ref); y+=26

    # Alt bant
    alt_y = H-100
    draw.line([(PAD,alt_y),(W-PAD,alt_y)],fill="#CCCCCC",width=1); alt_y+=4

    # QR
    qr_size=64; qr_x=W-PAD-qr_size
    if QR_OK:
        try:
            qr=qrcode.QRCode(box_size=2,border=1,error_correction=qrcode.constants.ERROR_CORRECT_L)
            qr.add_data(WP_LINK); qr.make(fit=True)
            qi=qr.make_image().resize((qr_size,qr_size),Image.Resampling.LANCZOS)
            img.paste(qi,(qr_x,alt_y+2))
        except: pass

    draw.text((PAD,alt_y+4),f"ID: {barkod_id}",fill="#1A1917",font=f_id); alt_y+=22

    # Barkod
    if BC_OK:
        bc_w=qr_x-PAD-4; bc_h=H-alt_y-PAD
        try:
            BC=barcode.get_barcode_class("code128")
            tmp=os.path.join(LABELS_DIR,f"_t_{str(barkod_id).replace('-','_')}")
            barcode.get_barcode_class("code128")(str(barkod_id),writer=ImageWriter()).save(
                tmp,{"write_text":False,"module_height":10,"quiet_zone":1})
            bi=Image.open(tmp+".png").resize((bc_w,max(bc_h,32)),Image.Resampling.LANCZOS)
            img.paste(bi,(PAD,alt_y))
            try: os.remove(tmp+".png")
            except: pass
        except: pass

    safe=str(barkod_id).replace("-","_")
    path=os.path.join(LABELS_DIR,f"e_{safe}.png")
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
