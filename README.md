# Ares Envanter Sistemi — Kurulum ve Kullanım Kılavuzu

## İçindekiler
1. [Gereksinimler](#gereksinimler)
2. [Kurulum](#kurulum)
3. [Google Sheets Bağlantısı](#google-sheets-bağlantısı)
4. [İlk Çalıştırma](#i̇lk-çalıştırma)
5. [Google Sheets Sekmeleri](#google-sheets-sekmeleri)
6. [Sık Sorulan Sorular](#sık-sorulan-sorular)
7. [Sorun Giderme](#sorun-giderme)

---

## Gereksinimler

### Bilgisayar
- Windows 10/11 (64-bit) veya Ubuntu 22+
- En az 4 GB RAM
- İnternet bağlantısı (Google Sheets için)

### Yazıcı
- Termal etiket yazıcı (TSC, Zebra vb.)
- Etiket boyutu: **30 × 40 mm**
- CUPS üzerinden tanımlı olması gerekir

---

## Kurulum

### Adım 1 — Python kurulumu (bir kez)

**Windows:**
1. https://python.org/downloads adresinden Python 3.11+ indirin
2. Kurulumda **"Add Python to PATH"** kutusunu işaretleyin
3. Kurulumu tamamlayın

**Ubuntu:**
```bash
sudo apt update && sudo apt install python3 python3-pip -y
```

### Adım 2 — Kütüphane kurulumu (bir kez)

`oto_envanter/` klasöründe terminal açın:

```bash
pip install PyQt6 pandas Pillow python-barcode qrcode gspread google-auth-oauthlib
```

### Adım 3 — Uygulamayı başlatın

```bash
cd oto_envanter
python3 main.py
```

> **Windows'ta:** `main.py` dosyasına çift tıklayarak da başlatılabilir.

---

## Google Sheets Bağlantısı

> Google Sheets bağlantısı **isteğe bağlıdır.** Bağlı olmadan uygulama tam çalışır,
> sadece satış/tur/stok verisi Sheets'e yazılmaz.

### Gerekli hesap ve izinler

- **Gmail hesabı gereklidir** — Google hesabınızla oturum açmanız istenir
- Okul veya kurumsal hesap sorunlara yol açabilir; **kişisel Gmail önerilir**
- Kurulum bilgisayarında tarayıcı (Chrome, Firefox) kurulu olmalıdır
- Bağlantı kurulduktan sonra token kaydedilir — her açılışta onay gerekmez

### Adım 1 — Google Cloud Console

1. https://console.cloud.google.com adresini açın
2. **Kişisel Gmail** hesabınızla giriş yapın
3. Sol üstten **"Yeni Proje"** oluşturun → Ad: `Ares Envanter`

### Adım 2 — API'leri etkinleştirin

1. Sol menü → **APIs & Services → Library**
2. **"Google Sheets API"** arayın → **Enable**
3. Geri dönün → **"Google Drive API"** arayın → **Enable**

### Adım 3 — OAuth izin ekranı

1. Sol menü → **APIs & Services → OAuth consent screen**
2. **External** seçin → **Create**
3. Uygulama adı: `Ares Envanter` → Kaydet
4. En alta inin → **"Test users"** bölümü → **"+ ADD USERS"**
5. Kendi Gmail adresinizi girin → **Save**

### Adım 4 — Kimlik bilgilerini oluşturun

1. Sol menü → **APIs & Services → Credentials**
2. **"+ CREATE CREDENTIALS"** → **OAuth client ID**
3. Application type: **Desktop app**
4. İsim: `Ares Desktop` → **Create**
5. Açılan pencereden **"DOWNLOAD JSON"** tıklayın
6. İndirilen dosyayı `oto_envanter/assets/` klasörüne kopyalayın
7. Dosya adını **`client_secret.json`** olarak değiştirin

### Adım 5 — Google Sheets tablosu

1. https://sheets.google.com adresini açın
2. **Yeni boş tablo** oluşturun
3. Tabloya bir isim verin (örn: `Ares Oto Envanter`)
4. Tarayıcının adres çubuğundaki **URL'nin tamamını** kopyalayın

### Adım 6 — Uygulamada bağlantı kurun

1. Uygulamayı açın → Sol menüden **⚙ Ayarlar**
2. Google Sheet URL alanına kopyaladığınız URL'yi yapıştırın
3. **"Kaydet & Bağlan"** butonuna tıklayın
4. Tarayıcı otomatik açılır → Gmail hesabınızla giriş yapın → **İzin verin**

> İlk bağlantıdan sonra `assets/oauth_token.json` dosyası oluşur.
> Bu dosya olduğu sürece her açılışta tarayıcı açılmaz.

---

## İlk Çalıştırma

### Mevcut stok varsa (daha önce kullanıldıysa)

```bash
# oto_envanter/ klasöründe çalıştırın
python3 migrate_db.py
python3 birimleri_olustur.py
python3 main.py
```

### Yeni kurulumda

```bash
python3 main.py
```
Veritabanı otomatik oluşturulur.

---

## Google Sheets Sekmeleri

Uygulama bağlandığında Google Sheets'te otomatik olarak 4 sekme oluşturulur:

| Sekme | İçerik | Ne Zaman Güncellenir |
|-------|--------|----------------------|
| **Stok_Genel** | Tüm stok listesi | Ayarlar → "Stok Güncelle" butonuyla elle |
| **Satışlar** | Satış kalemleri ve tutarlar | Her satış işleminde otomatik |
| **Tur_Programi** | Haftalık tur planı | Tur eklendiğinde/güncellendiğinde |
| **Mal_Girişleri** | Gelen mallar | Her mal girişinde otomatik |

> **Not:** Tura çıkış/dönüş detayları artık Sheets'e yazılmıyor;
> bu veriler yalnızca yerel veritabanında tutuluyor.

---

## Sık Sorulan Sorular

**S: Uygulama her açılışta internet ister mi?**
Hayır. Uygulama internetsiz çalışır. Sadece Google Sheets'e veri gönderirken internet gerekir.

**S: Aynı ağda başka bilgisayardan stok görülebilir mi?**
Telefon veya başka bilgisayarda Google Sheets'i açarak güncel stoku görebilirsiniz.
Sheets linki olan herkes "görüntüleyebilir" yetkisiyle erişebilir.

**S: Birden fazla kişi aynı anda kullanabilir mi?**
Uygulama tek bilgisayarda çalışır. Veriyi görmek için Google Sheets kullanılır,
değişiklik yapmak için uygulamanın kurulu olduğu bilgisayar gerekir.

**S: Veriler kaybolur mu?**
Veriler `ares.db` dosyasında saklanır. Bu dosyayı düzenli yedeklemeniz önerilir.

**S: Etiket yazıcı bağlı değilse ne olur?**
Etiket PNG olarak `labels/` klasörüne kaydedilir. Klasör otomatik açılır.

**S: Google bağlantısı kesilirse satışlar kaydedilir mi?**
Evet. Satışlar önce yerel veritabanına yazılır, Sheets bağlantısı kurulduğunda gönderilir.

---

## Sorun Giderme

### `NameError: name 'AresApp' is not defined`
→ `main.py` dosyası eski sürüm. Yeni `main.py`'yi indirip değiştirin.

### `QLineEdit is not defined`
→ `main.py` dosyası eski sürüm. Yeni `main.py`'yi indirip değiştirin.

### `sqlite3.OperationalError: no such column: birim_id`
→ Veritabanı güncellenmemiş. Şunu çalıştırın:
```bash
python3 migrate_db.py
python3 birimleri_olustur.py
```

### `Erişim engellendi: Hata 403`
→ Google'da kendinizi test kullanıcısı olarak eklemediniz.
OAuth consent screen → Test users → Gmail adresinizi ekleyin.

### `client_secret.json bulunamadı`
→ `assets/` klasörüne `client_secret.json` dosyasını kopyalamadınız.
Dosya adının tam olarak `client_secret.json` olduğundan emin olun.

### `ModuleNotFoundError`
→ Kütüphaneler kurulu değil:
```bash
pip install PyQt6 pandas Pillow python-barcode qrcode gspread google-auth-oauthlib
```

### Tarayıcı açılmıyor (Google onayı için)
→ `assets/oauth_token.json` dosyasını silin, uygulamayı yeniden açın.

### Etiket basılmıyor
→ Yazıcı CUPS'a tanımlı değil. Ubuntu'da:
```bash
lpstat -p  # yazıcıları listele
```
Yazıcı yoksa üretici sitesinden CUPS sürücüsünü kurun.

---

## Klasör Yapısı

```
oto_envanter/
├── main.py              ← Uygulama başlangıcı
├── ares.db              ← Veritabanı (yedekleyin!)
├── migrate_db.py        ← DB güncelleme scripti
├── birimleri_olustur.py ← Birim oluşturma scripti
├── assets/
│   ├── logo.png         ← Etiketlerde görünen logo
│   ├── client_secret.json  ← Google OAuth kimliği (siz koyacaksınız)
│   ├── oauth_token.json    ← Otomatik oluşur (silmeyin)
│   └── sheets_config.json  ← Sheets URL kaydı
├── labels/              ← Basılan etiket PNG'leri
├── core/
│   ├── database.py      ← Veritabanı şeması
│   ├── etiket.py        ← Etiket oluşturma
│   ├── sheets.py        ← Google Sheets bağlantısı
│   ├── tema.py          ← Renkler ve stiller
│   └── widgets.py       ← Ortak bileşenler
└── modules/
    ├── stok.py          ← Stok ve etiket yönetimi
    ├── tur.py           ← Tur yönetimi
    ├── hareketler.py    ← Satış ve mal girişi
    ├── genel.py         ← İstatistik ve eksik listesi
    ├── musteri.py       ← Müşteri listesi
    └── kargo.py         ← Kargo etiketleri
```
