"""Splash screen mínimo, dibujado en runtime (sin assets binarios)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QSplashScreen

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication


SPLASH_WIDTH = 420
SPLASH_HEIGHT = 240
BACKGROUND = "#1e1e2e"
FOREGROUND = "#cdd6f4"


def show_splash(app: QApplication) -> QSplashScreen:
    pixmap = QPixmap(SPLASH_WIDTH, SPLASH_HEIGHT)
    pixmap.fill(QColor(BACKGROUND))

    painter = QPainter(pixmap)
    try:
        painter.setPen(QColor(FOREGROUND))
        font = painter.font()
        font.setPointSize(28)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "pygit")
    finally:
        painter.end()

    splash = QSplashScreen(pixmap)
    splash.show()
    app.processEvents()
    return splash
