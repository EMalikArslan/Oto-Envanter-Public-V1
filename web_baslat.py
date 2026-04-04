"""
ARES Web Uygulaması — Başlatıcı
Kullanım: python web_baslat.py
Tarayıcı: http://localhost:5000
"""
from webapp.app import create_app

if __name__ == "__main__":
    app = create_app()
    print("\n" + "="*50)
    print("  ARES Web Uygulaması Başlatılıyor...")
    print("  Adres : http://localhost:5000")
    print("  Admin : admin@ares.com / admin123")
    print("="*50 + "\n")
    app.run(debug=True, host="0.0.0.0", port=5000)
