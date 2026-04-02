from PyQt6.QtWidgets import (QFrame, QLabel, QVBoxLayout, QHBoxLayout,
                             QWidget, QPushButton, QSizePolicy)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from core.tema import RENK


class StatKart(QFrame):
    """Üst kısımdaki istatistik kartları."""
    def __init__(self, baslik, deger, renk_hex, ikon=""):
        super().__init__()
        self.setObjectName("StatKart")
        self.setMinimumWidth(140)
        
        # Sol renk çubuğu
        self.setStyleSheet(f"""
            QFrame#StatKart {{
                background-color: {RENK['yuzey']};
                border-radius: 10px;
                border: 1px solid {RENK['cizgi']};
                border-left: 4px solid {renk_hex};
            }}
        """)
        
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(4)

        ust = QHBoxLayout()
        lbl_bas = QLabel(baslik.upper())
        lbl_bas.setStyleSheet(f"font-size: 10px; font-weight: 700; "
                              f"letter-spacing: 1.5px; color: {RENK['metin2']}; border: none;")
        ust.addWidget(lbl_bas)
        ust.addStretch()
        if ikon:
            lbl_ikon = QLabel(ikon)
            lbl_ikon.setStyleSheet(f"font-size: 16px; color: {renk_hex}; border: none;")
            ust.addWidget(lbl_ikon)
        lay.addLayout(ust)

        self.lbl_deger = QLabel(str(deger))
        self.lbl_deger.setStyleSheet(
            f"font-size: 28px; font-weight: 700; color: {RENK['metin']}; border: none;")
        lay.addWidget(self.lbl_deger)

    def set_deger(self, val):
        self.lbl_deger.setText(str(val))


class Badge(QLabel):
    """Renkli küçük rozet etiketi."""
    STILLER = {
        "yesil":  (RENK['yesil_bg'],  RENK['yesil']),
        "kirmizi":(RENK['aksan_bg'],  RENK['aksan']),
        "mavi":   (RENK['mavi_bg'],   RENK['mavi']),
        "sari":   (RENK['sari_bg'],   RENK['sari']),
        "gri":    (RENK['yuzey2'],    RENK['metin2']),
    }

    def __init__(self, metin, stil="gri"):
        super().__init__(metin)
        bg, fg = self.STILLER.get(stil, self.STILLER["gri"])
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {bg};
                color: {fg};
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }}
        """)
        self.setFixedHeight(20)


class SectionHeader(QWidget):
    """Modül içi bölüm başlığı."""
    def __init__(self, baslik, alt_baslik="", butonlar=None):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        sol = QVBoxLayout()
        sol.setSpacing(2)
        lbl = QLabel(baslik)
        lbl.setStyleSheet(
            f"font-size: 18px; font-weight: 700; color: {RENK['metin']};")
        sol.addWidget(lbl)
        if alt_baslik:
            lbl2 = QLabel(alt_baslik)
            lbl2.setStyleSheet(
                f"font-size: 11px; color: {RENK['metin2']}; letter-spacing: 0.5px;")
            sol.addWidget(lbl2)
        lay.addLayout(sol)
        lay.addStretch()

        if butonlar:
            for btn in butonlar:
                lay.addWidget(btn)


class AyiriciCizgi(QFrame):
    def __init__(self, dikey=False):
        super().__init__()
        self.setFrameShape(
            QFrame.Shape.VLine if dikey else QFrame.Shape.HLine)
        self.setStyleSheet(f"color: {RENK['cizgi']}; background: {RENK['cizgi']};")
        if dikey:
            self.setFixedWidth(1)
        else:
            self.setFixedHeight(1)


class BosBilgi(QWidget):
    """Tablo boş olduğunda gösterilen yardımcı widget."""
    def __init__(self, metin="Kayıt bulunamadı", alt=""):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl = QLabel("○")
        lbl.setStyleSheet(f"font-size: 40px; color: {RENK['cizgi_koyu']};")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(lbl)

        lbl2 = QLabel(metin)
        lbl2.setStyleSheet(f"font-size: 14px; font-weight: 600; color: {RENK['metin2']};")
        lbl2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(lbl2)

        if alt:
            lbl3 = QLabel(alt)
            lbl3.setStyleSheet(f"font-size: 12px; color: {RENK['metin3']};")
            lbl3.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(lbl3)
