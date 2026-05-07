"""Ventana principal.

Fase 0: estructura mínima con menubar (File/Edit/View/Repository/Help) y statusbar.
El widget central es un placeholder hasta que en Fase 1 se monten las vistas
(branches sidebar, graph, diff, commit panel).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QLabel, QMainWindow, QStatusBar

from pygit import __version__
from pygit.ui.i18n import gettext as _

if TYPE_CHECKING:
    from pygit.app.container import Services


class MainWindow(QMainWindow):
    """Shell principal de la aplicación."""

    def __init__(self, services: Services) -> None:
        super().__init__()
        self._services = services
        self.setWindowTitle(f"pygit {__version__}")
        self.resize(1280, 800)
        self._build_menus()
        self._build_statusbar()
        placeholder = QLabel(
            _("Open a repository to start"),
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        self.setCentralWidget(placeholder)

    def _build_menus(self) -> None:
        menubar = self.menuBar()
        if menubar is None:
            return

        file_menu = menubar.addMenu(_("&File"))
        action_open = QAction(_("&Open Repository..."), self)
        action_open.setShortcut(QKeySequence("Ctrl+Shift+O"))
        action_open.setStatusTip(_("Open an existing Git repository"))
        file_menu.addAction(action_open)
        file_menu.addSeparator()
        action_quit = QAction(_("&Quit"), self)
        action_quit.setShortcut(QKeySequence(QKeySequence.StandardKey.Quit))
        action_quit.triggered.connect(self.close)
        file_menu.addAction(action_quit)

        menubar.addMenu(_("&Edit"))
        menubar.addMenu(_("&View"))
        menubar.addMenu(_("&Repository"))

        help_menu = menubar.addMenu(_("&Help"))
        action_about = QAction(_("&About pygit"), self)
        help_menu.addAction(action_about)

    def _build_statusbar(self) -> None:
        bar = QStatusBar(self)
        self.setStatusBar(bar)
        bar.showMessage(_("Ready"))
