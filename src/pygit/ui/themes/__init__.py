"""Aplicación de temas a la ``QApplication``.

- ``dark``           → ``qdarkstyle`` (LGPL/MIT-friendly).
- ``light``          → JSON empaquetado en ``resources/themes/light.json``.
- ``high-contrast``  → JSON empaquetado en ``resources/themes/high-contrast.json``.
- Cualquier otro    → busca ``<name>.json`` en el mismo directorio.

La paleta del grafo se propaga al :class:`GraphDelegate` mediante
``current_graph_palette()`` — la MainWindow la consulta al aplicar el tema.
"""

from __future__ import annotations

from importlib import resources
from typing import TYPE_CHECKING

import qdarkstyle
import structlog

from pygit.ui.themes.loader import Theme, load_theme

if TYPE_CHECKING:
    from pathlib import Path

    from PySide6.QtWidgets import QApplication

_log = structlog.get_logger()

_current_graph_palette: list[str] = []


def current_graph_palette() -> list[str]:
    """Devuelve la paleta activa del grafo (vacía → paleta por defecto)."""
    return list(_current_graph_palette)


def apply_theme(app: QApplication, theme: str = "dark") -> None:
    global _current_graph_palette
    _current_graph_palette = []

    if theme == "dark":
        app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api="pyside6"))
        return

    theme_obj = _load_bundled_theme(theme)
    if theme_obj is None:
        # Fallback: no aplicamos nada, el default de Qt.
        _log.warning("theme not found, using Qt default", theme=theme)
        app.setStyleSheet("")
        return
    app.setStyleSheet(theme_obj.qss)
    _current_graph_palette = list(theme_obj.graph_palette)


def _load_bundled_theme(name: str) -> Theme | None:
    pkg = resources.files("pygit.resources.themes")
    candidate = pkg / f"{name}.json"
    if candidate.is_file():
        with resources.as_file(candidate) as path:
            return load_theme(_as_path(path))
    return None


def _as_path(path: object) -> Path:
    from pathlib import Path as _Path

    return _Path(str(path))


__all__ = ["apply_theme", "current_graph_palette"]
