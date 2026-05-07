"""Aplicación de temas a la ``QApplication``.

- ``dark``  → qdarkstyle (LGPL/MIT-friendly).
- otros     → carga ``<name>.qss`` desde ``pygit/resources/themes/``.

En Fase 0 sólo hay ``dark`` y un ``base.qss`` placeholder. Themes custom por
JSON (estilo SourceGit) llegarán en Fase 6.
"""

from __future__ import annotations

from importlib import resources
from typing import TYPE_CHECKING

import qdarkstyle

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication


def apply_theme(app: QApplication, theme: str = "dark") -> None:
    if theme == "dark":
        app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api="pyside6"))
        return
    qss = _load_qss(theme)
    app.setStyleSheet(qss)


def _load_qss(name: str) -> str:
    pkg = resources.files("pygit.resources.themes")
    candidate = pkg / f"{name}.qss"
    if candidate.is_file():
        return candidate.read_text(encoding="utf-8")
    return ""
