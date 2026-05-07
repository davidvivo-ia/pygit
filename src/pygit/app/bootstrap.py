"""Inicialización ordenada: logging, config, i18n, tema y contenedor de servicios."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pygit.app.container import Services
from pygit.infra.config import load_config
from pygit.infra.logging import configure_logging
from pygit.ui.i18n import install_translations
from pygit.ui.themes import apply_theme

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication


def bootstrap(app: QApplication) -> Services:
    """Configura subsistemas y devuelve el contenedor de servicios.

    Orden importante:

    1. Logging (estructurado) para que cualquier error posterior quede capturado.
    2. Config (TOML, ``platformdirs``) — fuente de verdad para idioma/tema.
    3. i18n (gettext) — antes de instanciar widgets que usen ``_()``.
    4. Tema (qdarkstyle / QSS propio) — antes de la primera ventana visible.
    """
    configure_logging()
    config = load_config()
    install_translations(language=config.ui.language)
    apply_theme(app, theme=config.ui.theme)
    return Services(config=config)
