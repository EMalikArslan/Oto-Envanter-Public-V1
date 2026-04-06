@echo off
chcp 65001 >nul 2>&1
title ARES Envanter — Kurulum Sihirbazı
color 0F
cls

echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║       ARES ENVANTER — KURULUM SİHİRBAZI              ║
echo  ║       Sürüm 1.0  ^|  Windows 10/11                    ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

:: ──────────────────────────────────────────────────────────────────────
:: YÖNETİCİ YETKİSİ
:: ──────────────────────────────────────────────────────────────────────
echo [ADIM 1/6]  Yönetici yetkisi kontrol ediliyor...
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo.
    echo  [!] Bu kurulum Yönetici yetkisi gerektirir.
    echo  setup.bat dosyasına SAĞ TIKLAYIN →
    echo  "Yönetici olarak çalıştır" seçeneğini seçin.
    echo.
    pause
    exit /b 1
)
echo  [OK] Yönetici yetkisi onaylandı.
echo.

:: ──────────────────────────────────────────────────────────────────────
:: PYTHON KONTROLÜ
:: ──────────────────────────────────────────────────────────────────────
echo [ADIM 2/6]  Python 3.11+ kontrol ediliyor...
where python >nul 2>&1
if %errorLevel% neq 0 (
    echo.
    echo  [!] Python bulunamadi!
    echo      Indirme sayfasi aciliyor...
    echo.
    echo  ONEMLI: Kurulumda
    echo   [x] "Add Python to PATH"
    echo   [x] "Install for all users"
    echo  kutularini MUTLAKA isaretleyin!
    echo.
    start https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
    echo  Python kurulumu tamamlayip bu pencereye donun,
    echo  ardindan ENTER'a basin...
    pause >nul
    where python >nul 2>&1
    if %errorLevel% neq 0 (
        echo  [HATA] Python hala bulunamadi. Kurulumu kontrol edin.
        pause
        exit /b 1
    )
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo  [OK] %PY_VER% hazir.
echo.

:: ──────────────────────────────────────────────────────────────────────
:: HEDEF KLASÖR
:: ──────────────────────────────────────────────────────────────────────
echo [ADIM 3/6]  Kurulum klasoru ayarlaniyor...
set HEDEF=C:\AresEnvanter
if not exist "%HEDEF%" mkdir "%HEDEF%"
echo  [OK] Klasor: %HEDEF%
echo.

:: ──────────────────────────────────────────────────────────────────────
:: DOSYALARI KOPYALA
:: ──────────────────────────────────────────────────────────────────────
echo [ADIM 4/6]  Dosyalar kopyalaniyor...
xcopy /E /I /Y /Q "%~dp0." "%HEDEF%\" >nul 2>&1
if %errorLevel% neq 0 (
    echo  [HATA] Kopyalama basarisiz!
    pause
    exit /b 1
)
echo  [OK] Kopyalama tamamlandi.
echo.

:: ──────────────────────────────────────────────────────────────────────
:: PYTHON PAKETLERİ
:: ──────────────────────────────────────────────────────────────────────
echo [ADIM 5/6]  Python paketleri yukleniyor (internet gerekli, ~5 dk)...
echo.
python -m pip install --upgrade pip --quiet

echo  [1/6] PyQt6 (arayuz)...
python -m pip install "PyQt6>=6.4.0" --quiet
if %errorLevel% neq 0 ( echo  [HATA] PyQt6 yuklenemedi! & pause & exit /b 1 )

echo  [2/6] Pandas + Openpyxl (veri)...
python -m pip install "pandas>=2.0.0" "openpyxl>=3.1.2" --quiet

echo  [3/6] Pillow + Barkod + QR...
python -m pip install "Pillow>=10.0.0" "python-barcode>=0.15.1" "qrcode[pil]>=7.4.2" --quiet

echo  [4/6] Google Sheets...
python -m pip install "gspread>=5.12.0" "google-auth-oauthlib>=1.2.0" --quiet

echo  [5/6] Flask (web uygulamasi)...
python -m pip install "Flask>=3.0.0" "Flask-Login>=0.6.3" "Werkzeug>=3.0.0" --quiet

echo  [6/6] Tum paketler yuklendi!
echo.
echo  [OK] Paket kurulumu tamamlandi.
echo.

:: ──────────────────────────────────────────────────────────────────────
:: BAŞLATICI DOSYALARI OLUŞTUR
:: ──────────────────────────────────────────────────────────────────────
echo [ADIM 6/6]  Baslatiicilar olusturuluyor...

:: Masaüstü uygulaması VBS başlatıcı (konsol penceresi gizli)
set VBS=%HEDEF%\baslat.vbs
(
echo Set sh = CreateObject^("WScript.Shell"^)
echo sh.CurrentDirectory = "%HEDEF%"
echo sh.Run "pythonw main.py", 0, False
) > "%VBS%"

:: Web uygulaması başlatıcı
set WEB_BAT=%HEDEF%\web_baslat_win.bat
(
echo @echo off
echo chcp 65001 ^>nul 2^>^&1
echo title ARES Web Uygulamasi
echo cd /d "%HEDEF%"
echo echo.
echo echo  ARES Web Uygulamasi baslatiliyor...
echo echo  Tarayicida acin: http://localhost:5000
echo echo  Kapatmak icin bu pencereyi kapatin.
echo echo.
echo python web_baslat.py
echo pause
) > "%WEB_BAT%"

:: Masaüstü kısayolu — Masaüstü Uygulaması
set KISAYOL1=%USERPROFILE%\Desktop\Ares Envanter.lnk
powershell -NoProfile -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut('%KISAYOL1%');$s.TargetPath='wscript.exe';$s.Arguments='\"%VBS%\"';$s.WorkingDirectory='%HEDEF%';$s.Description='Ares Envanter Masaustu';$s.Save()" >nul 2>&1

:: Masaüstü kısayolu — Web Uygulaması
set KISAYOL2=%USERPROFILE%\Desktop\Ares Web.lnk
powershell -NoProfile -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut('%KISAYOL2%');$s.TargetPath='%WEB_BAT%';$s.WorkingDirectory='%HEDEF%';$s.Description='Ares Web Uygulamasi';$s.Save()" >nul 2>&1

echo  [OK] Kisayollar olusturuldu.
echo.

:: ──────────────────────────────────────────────────────────────────────
:: TAMAMLANDI
:: ──────────────────────────────────────────────────────────────────────
cls
echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║        KURULUM BASARIYLA TAMAMLANDI!                 ║
echo  ╚══════════════════════════════════════════════════════╝
echo.
echo  Kurulum Yeri  : %HEDEF%
echo.
echo  Masaustunde 2 kisayol olusturuldu:
echo.
echo  [*] "Ares Envanter"  → Masaustu uygulamasi (PyQt6)
echo  [*] "Ares Web"       → Web arayuzu (http://localhost:5000)
echo.
echo  ─────────────────────────────────────────────────────
echo  Web Giris Bilgileri:
echo    E-posta : admin@ares.com
echo    Sifre   : admin123
echo  ─────────────────────────────────────────────────────
echo.
echo  Google Sheets (opsiyonel):
echo    assets\client_secret.json dosyasini ekleyin
echo    Sonra Ayarlar sayfasindan yapilandirin
echo.

set /p CEVAP=Masaustu uygulamasini simdi baslatmak ister misiniz? (E/H):
if /i "%CEVAP%"=="E" (
    wscript.exe "%VBS%"
    echo  Uygulama baslatildi!
)

set /p CEVAP2=Web uygulamasini simdi baslatmak ister misiniz? (E/H):
if /i "%CEVAP2%"=="E" (
    start "" "%WEB_BAT%"
    timeout /t 3 >nul
    start http://localhost:5000
)

echo.
echo  Iyi kullanimlar!
echo.
pause
