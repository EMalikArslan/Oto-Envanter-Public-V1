#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
#  ARES ENVANTER — Ubuntu 24 Kurulum Sihirbazı
#  Kullanım: chmod +x kurulum_ubuntu.sh && ./kurulum_ubuntu.sh
# ═══════════════════════════════════════════════════════════════════════════

set -e  # Hata olursa dur

# ── Renkler ──────────────────────────────────────────────────────────────────
GRN='\033[0;32m'
YEL='\033[1;33m'
RED='\033[0;31m'
BLU='\033[0;34m'
CYN='\033[0;36m'
NC='\033[0m'  # Renk sıfırla

ok()  { echo -e "${GRN}  [✓] $1${NC}"; }
err() { echo -e "${RED}  [✗] $1${NC}"; exit 1; }
inf() { echo -e "${CYN}  [→] $1${NC}"; }
wrn() { echo -e "${YEL}  [!] $1${NC}"; }

# ── Başlık ────────────────────────────────────────────────────────────────────
clear
echo ""
echo -e "${BLU}  ╔══════════════════════════════════════════════════════╗"
echo -e "  ║       ARES ENVANTER — KURULUM SİHİRBAZI              ║"
echo -e "  ║       Ubuntu 24.04 LTS  |  Sürüm 1.0                 ║"
echo -e "  ╚══════════════════════════════════════════════════════╝${NC}"
echo ""

# ── Çalışma dizini ────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$HOME/AresEnvanter"
inf "Kaynak klasör : $SCRIPT_DIR"
inf "Kurulum yeri  : $INSTALL_DIR"
echo ""

# ── Sudo kontrolü ─────────────────────────────────────────────────────────────
echo "[ADIM 1/7]  Sudo yetkisi kontrol ediliyor..."
if ! sudo -v 2>/dev/null; then
    err "sudo yetkisi gerekli. Kullanıcınızın sudo grubunda olduğundan emin olun."
fi
ok "Sudo yetkisi onaylandı."
echo ""

# ── Sistem güncellemesi ───────────────────────────────────────────────────────
echo "[ADIM 2/7]  Sistem paketleri güncelleniyor..."
inf "apt update çalıştırılıyor..."
sudo apt-get update -qq
ok "Paket listesi güncellendi."
echo ""

# ── Sistem bağımlılıkları ─────────────────────────────────────────────────────
echo "[ADIM 3/7]  Sistem bağımlılıkları kuruluyor..."

inf "Python 3, pip, venv..."
sudo apt-get install -y -qq \
    python3 python3-pip python3-venv python3-dev

inf "PyQt6 sistem kütüphaneleri..."
sudo apt-get install -y -qq \
    libgl1-mesa-glx libglib2.0-0 libdbus-1-3 \
    libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
    libxcb-randr0 libxcb-render-util0 libxcb-xinerama0 libxcb-xkb1 \
    libxkbcommon-x11-0 libfontconfig1 libfreetype6 \
    x11-apps mesa-utils 2>/dev/null || true

inf "Türkçe font desteği..."
sudo apt-get install -y -qq \
    fonts-dejavu-core fonts-liberation fonts-ubuntu 2>/dev/null || true

ok "Sistem bağımlılıkları tamamlandı."
echo ""

# ── Python sürüm kontrolü ─────────────────────────────────────────────────────
echo "[ADIM 4/7]  Python sürümü kontrol ediliyor..."
PY_VER=$(python3 --version 2>&1)
inf "$PY_VER"
MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")
if [ "$MAJOR" -lt 3 ] || { [ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 10 ]; }; then
    err "Python 3.10+ gerekli. Mevcut: $PY_VER"
fi
ok "Python sürümü uygun: $PY_VER"
echo ""

# ── Klasörleri hazırla ────────────────────────────────────────────────────────
echo "[ADIM 5/7]  Kurulum klasörü hazırlanıyor..."
if [ "$SCRIPT_DIR" != "$INSTALL_DIR" ]; then
    mkdir -p "$INSTALL_DIR"
    cp -r "$SCRIPT_DIR/." "$INSTALL_DIR/"
    inf "Dosyalar kopyalandı: $INSTALL_DIR"
else
    inf "Dosyalar zaten yerinde: $INSTALL_DIR"
fi

mkdir -p "$INSTALL_DIR/labels"
mkdir -p "$INSTALL_DIR/assets"
mkdir -p "$INSTALL_DIR/logs"
mkdir -p "$INSTALL_DIR/webapp/static/img/urunler"
ok "Klasörler hazır."
echo ""

# ── Sanal ortam + pip paketleri ───────────────────────────────────────────────
echo "[ADIM 6/7]  Python paketleri kuruluyor..."

VENV_DIR="$INSTALL_DIR/venv"
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    inf "Sanal ortam oluşturuldu: $VENV_DIR"
else
    inf "Mevcut sanal ortam kullanılıyor: $VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

inf "[1/6] pip güncelleniyor..."
pip install --upgrade pip --quiet

inf "[2/6] PyQt6..."
pip install "PyQt6>=6.4.0" --quiet || err "PyQt6 yüklenemedi!"

inf "[3/6] Pandas + Openpyxl..."
pip install "pandas>=2.0.0" "openpyxl>=3.1.2" --quiet

inf "[4/6] Pillow + Barkod + QR..."
pip install "Pillow>=10.0.0" "python-barcode>=0.15.1" "qrcode[pil]>=7.4.2" --quiet

inf "[5/6] Google Sheets..."
pip install "gspread>=5.12.0" "google-auth-oauthlib>=1.2.0" --quiet

inf "[6/6] Flask (web uygulaması)..."
pip install "Flask>=3.0.0" "Flask-Login>=0.6.3" "Werkzeug>=3.0.0" --quiet

ok "Tüm paketler yüklendi."
echo ""

# ── Başlatıcı scriptler ───────────────────────────────────────────────────────
echo "[ADIM 7/7]  Başlatıcılar oluşturuluyor..."

# Masaüstü uygulaması başlatıcı
LAUNCHER="$INSTALL_DIR/ares_baslat.sh"
cat > "$LAUNCHER" << SCRIPT
#!/usr/bin/env bash
cd "$INSTALL_DIR"
source "$VENV_DIR/bin/activate"
export QT_QPA_PLATFORM=xcb
export QT_FONT_DPI=96
python main.py "\$@"
SCRIPT
chmod +x "$LAUNCHER"

# Web uygulaması başlatıcı
WEB_LAUNCHER="$INSTALL_DIR/ares_web_baslat.sh"
cat > "$WEB_LAUNCHER" << SCRIPT
#!/usr/bin/env bash
cd "$INSTALL_DIR"
source "$VENV_DIR/bin/activate"
echo ""
echo "  ARES Web Uygulaması başlatılıyor..."
echo "  Tarayıcıda açın: http://localhost:5000"
echo "  Durdurmak için Ctrl+C"
echo ""
python web_baslat.py
SCRIPT
chmod +x "$WEB_LAUNCHER"

# .desktop dosyası — Masaüstü uygulaması
DESKTOP_APP="$HOME/.local/share/applications/ares-envanter.desktop"
mkdir -p "$HOME/.local/share/applications"
cat > "$DESKTOP_APP" << DESKTOP
[Desktop Entry]
Version=1.0
Type=Application
Name=Ares Envanter
Comment=Ares Oto Elektronik Envanter Sistemi
Exec=$LAUNCHER
Icon=$INSTALL_DIR/assets/logo.png
Terminal=false
Categories=Office;Finance;
StartupWMClass=ares
DESKTOP
chmod +x "$DESKTOP_APP"

# .desktop dosyası — Web uygulaması
DESKTOP_WEB="$HOME/.local/share/applications/ares-web.desktop"
cat > "$DESKTOP_WEB" << DESKTOP
[Desktop Entry]
Version=1.0
Type=Application
Name=Ares Web
Comment=Ares Envanter Web Arayüzü
Exec=bash -c "$WEB_LAUNCHER & sleep 3 && xdg-open http://localhost:5000"
Icon=$INSTALL_DIR/assets/logo.png
Terminal=true
Categories=Office;Finance;
DESKTOP
chmod +x "$DESKTOP_WEB"

# Masaüstüne kısayol kopyala (varsa)
if [ -d "$HOME/Desktop" ]; then
    cp "$DESKTOP_APP" "$HOME/Desktop/ares-envanter.desktop"
    cp "$DESKTOP_WEB" "$HOME/Desktop/ares-web.desktop"
    chmod +x "$HOME/Desktop/ares-envanter.desktop" 2>/dev/null || true
    chmod +x "$HOME/Desktop/ares-web.desktop" 2>/dev/null || true
fi

ok "Başlatıcılar oluşturuldu."
echo ""

# ── Kurulum özeti ─────────────────────────────────────────────────────────────
echo ""
echo -e "${GRN}  ╔══════════════════════════════════════════════════════╗"
echo -e "  ║       KURULUM BAŞARIYLA TAMAMLANDI!                  ║"
echo -e "  ╚══════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${CYN}Kurulum Yeri : ${NC}$INSTALL_DIR"
echo -e "  ${CYN}Sanal Ortam  : ${NC}$VENV_DIR"
echo ""
echo -e "  ${YEL}Başlatma Komutları:${NC}"
echo -e "  ${GRN}  Masaüstü Uygulaması:${NC}"
echo    "    $LAUNCHER"
echo -e "  ${GRN}  Web Uygulaması:${NC}"
echo    "    $WEB_LAUNCHER"
echo    "    Sonra: http://localhost:5000"
echo ""
echo -e "  ${YEL}Web Giriş Bilgileri:${NC}"
echo    "    E-posta : admin@ares.com"
echo    "    Şifre   : admin123"
echo ""
echo -e "  ${YEL}Google Sheets (opsiyonel):${NC}"
echo    "    $INSTALL_DIR/assets/client_secret.json"
echo    "    ekleyin, ardından Ayarlar sayfasından yapılandırın."
echo ""

# Şimdi başlat?
read -r -p "  Masaüstü uygulamasını şimdi başlatmak ister misiniz? (e/H): " CEVAP
if [[ "$CEVAP" =~ ^[Ee]$ ]]; then
    inf "Uygulama başlatılıyor..."
    nohup "$LAUNCHER" >/dev/null 2>&1 &
    ok "Başlatıldı! (arka planda çalışıyor)"
fi

read -r -p "  Web uygulamasını şimdi başlatmak ister misiniz? (e/H): " CEVAP2
if [[ "$CEVAP2" =~ ^[Ee]$ ]]; then
    inf "Web sunucusu başlatılıyor..."
    nohup "$WEB_LAUNCHER" >/dev/null 2>&1 &
    sleep 3
    xdg-open http://localhost:5000 2>/dev/null || inf "Tarayıcıda http://localhost:5000 adresini açın."
    ok "Web sunucusu başlatıldı!"
fi

echo ""
echo -e "${GRN}  İyi kullanımlar!${NC}"
echo ""
