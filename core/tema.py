# ── ARES ENVANTER — TEMA ──────────────────────────────────────────────────
# Estetik: Industrial Precision — siyah/beyaz/gri baz + tek aksan rengi (kırmızı)
# Yazıtipi: Sistem fontlarından DM Sans veya Ubuntu kullanılır

RENK = {
    "zemin":        "#F4F3F0",   # sıcak krem — ana arka plan
    "yuzey":        "#FFFFFF",   # kartlar, paneller
    "yuzey2":       "#EDECEA",   # hafif gri yüzey
    "cizgi":        "#D6D4CE",   # ince ayırıcılar
    "cizgi_koyu":   "#B0AEA7",   # daha belirgin kenarlık
    "metin":        "#1A1917",   # ana metin — neredeyse siyah
    "metin2":       "#6B6861",   # ikincil metin
    "metin3":       "#A09E99",   # ipucu/placeholder
    "aksan":        "#C0392B",   # ARES kırmızısı — tek canlı renk
    "aksan2":       "#E74C3C",   # hover aksan
    "aksan_bg":     "#FDECEA",   # aksan arkaplan (soft)
    "yesil":        "#27AE60",   # başarı / stokta var
    "yesil_bg":     "#E8F8F0",
    "mavi":         "#2471A3",   # bilgi
    "mavi_bg":      "#EAF4FB",
    "sari":         "#D4AC0D",   # uyarı / bekleyen
    "sari_bg":      "#FEF9E7",
    "koyu_zemin":   "#1A1917",   # sidebar arka plan
    "koyu_yuzey":   "#252320",
    "koyu_metin":   "#F4F3F0",
    "koyu_metin2":  "#A09E99",
    "koyu_aksan":   "#E74C3C",
}

BOYUT = {
    "radius_sm":    "4px",
    "radius_md":    "8px",
    "radius_lg":    "12px",
    "sidebar_w":    220,
    "header_h":     60,
}

def get_stylesheet():
    r = RENK
    return f"""
/* ── GENEL ── */
QWidget {{
    font-family: 'Ubuntu', 'Segoe UI', 'DM Sans', sans-serif;
    font-size: 13px;
    color: {r['metin']};
    background-color: {r['zemin']};
}}
QMainWindow {{
    background-color: {r['zemin']};
}}

/* ── SIDEBAR ── */
QWidget#Sidebar {{
    background-color: {r['koyu_zemin']};
    border-right: 1px solid #2E2C29;
}}
QLabel#SidebarLogo {{
    color: {r['koyu_metin']};
    font-size: 18px;
    font-weight: 700;
    letter-spacing: 2px;
    padding: 0px 0px 4px 0px;
}}
QLabel#SidebarAlt {{
    color: {r['koyu_metin2']};
    font-size: 10px;
    letter-spacing: 3px;
}}
QPushButton#NavBtn {{
    background-color: transparent;
    color: {r['koyu_metin2']};
    border: none;
    border-radius: 6px;
    text-align: left;
    padding: 10px 16px;
    font-size: 13px;
    font-weight: 500;
}}
QPushButton#NavBtn:hover {{
    background-color: {r['koyu_yuzey']};
    color: {r['koyu_metin']};
}}
QPushButton#NavBtn[active="true"] {{
    background-color: {r['aksan']};
    color: #FFFFFF;
    font-weight: 700;
}}

/* ── HEADER ── */
QWidget#Header {{
    background-color: {r['yuzey']};
    border-bottom: 1px solid {r['cizgi']};
}}
QLabel#HeaderBaslik {{
    font-size: 18px;
    font-weight: 700;
    color: {r['metin']};
    letter-spacing: 0.5px;
}}
QLabel#HeaderAlt {{
    font-size: 11px;
    color: {r['metin2']};
    letter-spacing: 1px;
}}

/* ── KART ── */
QFrame#Kart {{
    background-color: {r['yuzey']};
    border-radius: 10px;
    border: 1px solid {r['cizgi']};
}}
QFrame#KartKoyu {{
    background-color: {r['zemin']};
    border-radius: 8px;
    border: 1px solid {r['cizgi']};
}}

/* ── TABLO ── */
QTableWidget {{
    background-color: {r['yuzey']};
    gridline-color: {r['cizgi']};
    border: 1px solid {r['cizgi']};
    border-radius: 8px;
    selection-background-color: {r['aksan_bg']};
    selection-color: {r['metin']};
    font-size: 13px;
    alternate-background-color: {r['zemin']};
}}
QTableWidget::item {{
    padding: 6px 10px;
    border: none;
}}
QTableWidget::item:selected {{
    background-color: {r['aksan_bg']};
    color: {r['metin']};
}}
QHeaderView::section {{
    background-color: {r['yuzey2']};
    color: {r['metin2']};
    padding: 8px 10px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
    border: none;
    border-right: 1px solid {r['cizgi']};
    border-bottom: 1px solid {r['cizgi']};
}}
QHeaderView::section:first {{
    border-top-left-radius: 8px;
}}

/* ── BUTONLAR ── */
QPushButton {{
    background-color: {r['metin']};
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 9px 20px;
    font-size: 13px;
    font-weight: 600;
}}
QPushButton:hover {{
    background-color: #2D2C29;
}}
QPushButton:pressed {{
    background-color: {r['aksan']};
}}
QPushButton#BtnIkincil {{
    background-color: transparent;
    color: {r['metin']};
    border: 1.5px solid {r['cizgi_koyu']};
}}
QPushButton#BtnIkincil:hover {{
    border-color: {r['metin']};
    background-color: {r['yuzey2']};
}}
QPushButton#BtnAksan {{
    background-color: {r['aksan']};
    color: #FFFFFF;
}}
QPushButton#BtnAksan:hover {{
    background-color: {r['aksan2']};
}}
QPushButton#BtnBasarili {{
    background-color: {r['yesil']};
    color: #FFFFFF;
}}
QPushButton#BtnTehlike {{
    background-color: transparent;
    color: {r['aksan']};
    border: 1.5px solid {r['aksan']};
}}
QPushButton#BtnTehlike:hover {{
    background-color: {r['aksan_bg']};
}}

/* ── GİRDİLER ── */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {r['yuzey']};
    color: {r['metin']};
    border: 1.5px solid {r['cizgi']};
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 13px;
    selection-background-color: {r['aksan_bg']};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {r['metin']};
    background-color: {r['yuzey']};
}}
QLineEdit::placeholder {{ color: {r['metin3']}; }}

QComboBox {{
    background-color: {r['yuzey']};
    color: {r['metin']};
    border: 1.5px solid {r['cizgi']};
    border-radius: 6px;
    padding: 7px 12px;
    font-size: 13px;
    min-height: 20px;
}}
QComboBox:focus {{ border-color: {r['metin']}; }}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {r['metin2']};
    margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background-color: {r['yuzey']};
    border: 1px solid {r['cizgi_koyu']};
    border-radius: 6px;
    selection-background-color: {r['aksan_bg']};
    selection-color: {r['metin']};
    padding: 4px;
}}

QSpinBox {{
    background-color: {r['yuzey']};
    color: {r['metin']};
    border: 1.5px solid {r['cizgi']};
    border-radius: 6px;
    padding: 7px 12px;
    font-size: 13px;
}}
QSpinBox:focus {{ border-color: {r['metin']}; }}
QSpinBox::up-button, QSpinBox::down-button {{ width: 20px; border: none; }}

/* ── SCROLL ── */
QScrollBar:vertical {{
    background: {r['zemin']};
    width: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {r['cizgi_koyu']};
    border-radius: 4px;
    min-height: 40px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ height: 8px; background: {r['zemin']}; border-radius: 4px; }}
QScrollBar::handle:horizontal {{ background: {r['cizgi_koyu']}; border-radius: 4px; }}

/* ── AYIRICI ── */
QFrame[frameShape="4"], QFrame[frameShape="5"] {{
    color: {r['cizgi']};
}}

/* ── SEKME ── */
QTabWidget::pane {{
    border: 1px solid {r['cizgi']};
    border-radius: 0 8px 8px 8px;
    background: {r['yuzey']};
}}
QTabBar::tab {{
    background: {r['yuzey2']};
    color: {r['metin2']};
    border: 1px solid {r['cizgi']};
    border-bottom: none;
    padding: 8px 20px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.5px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}}
QTabBar::tab:selected {{
    background: {r['yuzey']};
    color: {r['metin']};
    border-bottom-color: {r['yuzey']};
}}
QTabBar::tab:hover:!selected {{
    background: {r['zemin']};
    color: {r['metin']};
}}

/* ── CHECKBOX ── */
QCheckBox {{
    spacing: 8px;
    font-size: 13px;
    color: {r['metin']};
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1.5px solid {r['cizgi_koyu']};
    background: {r['yuzey']};
}}
QCheckBox::indicator:checked {{
    background-color: {r['metin']};
    border-color: {r['metin']};
}}

/* ── MESAJ KUTUSU ── */
QMessageBox {{
    background-color: {r['yuzey']};
}}

/* ── ETIKET/LABEL ── */
QLabel#EtiketBaslik {{
    font-size: 22px;
    font-weight: 700;
    color: {r['metin']};
}}
QLabel#EtiketKucuk {{
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1.5px;
    color: {r['metin2']};
}}

/* ── STAT KART ── */
QFrame#StatKart {{
    background-color: {r['yuzey']};
    border-radius: 10px;
    border: 1px solid {r['cizgi']};
    padding: 4px;
}}
"""
