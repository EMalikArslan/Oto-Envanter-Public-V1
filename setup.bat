@echo off
chcp 65001 >nul 2>&1
title Ares Envanter Kurulum

echo.
echo  ============================================
echo   ARES ENVANTER -- KURULUM BASLADI
echo  ============================================
echo.

:: Adim 1: Yonetici kontrolu
echo [ADIM 1] Yonetici yetkisi kontrol ediliyor...
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo.
    echo  [HATA] Yonetici yetkisi yok!
    echo  setup.bat dosyasina SAG TIKLAYIN
    echo  ve "Yonetici olarak calistir" secin.
    echo.
    pause
    exit /b 1
)
echo  [OK] Yonetici yetkisi var.

:: Adim 2: Python kontrolu
echo.
echo [ADIM 2] Python kontrol ediliyor...
where python >nul 2>&1
if %errorLevel% neq 0 (
    echo  [!] Python bulunamadi. Indirme sayfasi aciliyor...
    echo.
    echo  ONEMLI: Kurulumda "Add Python to PATH"
    echo  kutusunu MUTLAKA isaretleyin!
    echo.
    start https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
    echo  Python kurulumu bitince ENTER'a basin...
    pause >nul
    where python >nul 2>&1
    if %errorLevel% neq 0 (
        echo  [HATA] Python hala bulunamadi!
        pause
        exit /b 1
    )
)
python --version
echo  [OK] Python hazir.

:: Adim 3: Paketler
echo.
echo [ADIM 3] Paketler yukleniyor (internet gerekli, 3-5 dk)...
echo.
python -m pip install --upgrade pip --quiet
python -m pip install PyQt6 pandas Pillow python-barcode "qrcode[pil]" gspread google-auth-oauthlib
if %errorLevel% neq 0 (
    echo.
    echo  [HATA] Paket yuklemesi basarisiz!
    echo  Internet baglantinizi kontrol edin.
    pause
    exit /b 1
)
echo  [OK] Tum paketler yuklendi.

:: Adim 4: Dosyalari kopyala
echo.
echo [ADIM 4] Dosyalar C:\AresEnvanter klasorune kopyalaniyor...
set HEDEF=C:\AresEnvanter
if not exist "%HEDEF%" mkdir "%HEDEF%"
xcopy /E /I /Y "%~dp0." "%HEDEF%\" >nul
echo  [OK] Kopyalama tamamlandi.

:: Adim 5: Baslatici olustur
echo.
echo [ADIM 5] Masaustu kisayolu olusturuluyor...

set VBS=%HEDEF%\baslat.vbs
(
echo Set sh = CreateObject^("WScript.Shell"^)
echo sh.CurrentDirectory = "%HEDEF%"
echo sh.Run "pythonw main.py", 0, False
) > "%VBS%"

set KISAYOL=%USERPROFILE%\Desktop\Ares Envanter.lnk
powershell -NoProfile -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut('%KISAYOL%');$s.TargetPath='wscript.exe';$s.Arguments='\"%VBS%\"';$s.WorkingDirectory='%HEDEF%';$s.Description='Ares Envanter';$s.Save()"

echo  [OK] Kisayol olusturuldu.

echo.
echo  ============================================
echo   KURULUM TAMAMLANDI!
echo  ============================================
echo.
echo  Klasor  : C:\AresEnvanter
echo  Kisayol : Masaustundeki "Ares Envanter"
echo.
echo  NOT: Google Sheets icin
echo  C:\AresEnvanter\assets\ klasorune
echo  client_secret.json dosyasini kopyalayin.
echo.

set /p CEVAP=Simdi baslatmak ister misiniz? (E/H): 
if /i "%CEVAP%"=="E" (
    wscript.exe "%VBS%"
)

echo.
pause
