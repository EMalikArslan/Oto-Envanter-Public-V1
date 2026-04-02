"""
build_exe.py — Ares Envanter Windows .exe Paketleyici
======================================================
Çalıştırmak için (oto_envanter/ klasöründe):

  pip install pyinstaller
  python build_exe.py

Çıktı: dist/AresEnvanter/AresEnvanter.exe
"""

import subprocess, sys, os, shutil

BASE = os.path.dirname(__file__)
DIST = os.path.join(BASE, "dist")
BUILD = os.path.join(BASE, "build")

# Temizle
for d in [DIST, BUILD]:
    if os.path.exists(d):
        shutil.rmtree(d)
        print(f"✓ {d} temizlendi")

# Dahil edilecek dosyalar (assets klasörü)
assets = os.path.join(BASE, "assets")

cmd = [
    sys.executable, "-m", "PyInstaller",
    "--name", "AresEnvanter",
    "--onedir",               # tek klasör (onefile yerine — daha hızlı açılır)
    "--windowed",             # konsol penceresi yok
    "--noconfirm",
    "--clean",

    # İkon (varsa)
    # "--icon", os.path.join(assets, "ikon.ico"),

    # Gizli importlar
    "--hidden-import", "PIL._tkinter_finder",
    "--hidden-import", "barcode.writer",
    "--hidden-import", "qrcode.image.pil",
    "--hidden-import", "flask",
    "--hidden-import", "werkzeug",
    "--hidden-import", "jinja2",
    "--hidden-import", "sqlite3",
    "--hidden-import", "pandas",

    # Assets klasörünü dahil et
    "--add-data", f"{assets}{os.pathsep}assets",

    # Web sunucu şablonları için (Flask inline template kullandık, gerek yok)
    # "--add-data", f"{os.path.join(BASE,'templates')}{os.pathsep}templates",

    os.path.join(BASE, "main.py"),
]

print("Derleniyor... (2-5 dakika sürebilir)")
print(" ".join(cmd))
print()

result = subprocess.run(cmd, cwd=BASE)

if result.returncode == 0:
    exe_yolu = os.path.join(DIST, "AresEnvanter", "AresEnvanter.exe")
    print(f"""
╔══════════════════════════════════════════════════════╗
║              DERLEME BAŞARILI!                       ║
╠══════════════════════════════════════════════════════╣
║                                                      ║
║  Exe konumu:                                         ║
║  dist/AresEnvanter/AresEnvanter.exe                  ║
║                                                      ║
║  Dağıtmak için:                                      ║
║  dist/AresEnvanter/ klasörünün TAMAMINI kopyalayın   ║
║  (sadece .exe değil, klasörün tümü gerekli)          ║
║                                                      ║
║  İlk çalıştırmada ares.db otomatik oluşur.           ║
╚══════════════════════════════════════════════════════╝
""")
else:
    print(f"""
╔══════════════════════════════════════════════════════╗
║              DERLEME HATASI!                         ║
╠══════════════════════════════════════════════════════╣
║  Yukarıdaki hata mesajını inceleyin.                 ║
║  Sık sorun: pip install pyinstaller --upgrade        ║
╚══════════════════════════════════════════════════════╝
""")
    sys.exit(1)
