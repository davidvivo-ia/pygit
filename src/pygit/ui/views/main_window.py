"""Ventana principal.

Fase 1.1: aparte del menubar, la ventana ya orquesta apertura de repos.
``Open Repository...`` lanza un ``QFileDialog``, instancia un
``RepositoryVM`` con los servicios del bootstrap y monta una
``RepositoryView`` en el área central. El placeholder se muestra cuando no
hay repo abierto.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QStatusBar,
)

from pygit import __version__
from pygit.domain.git.models import HeadInfo
from pygit.ui.i18n import gettext as _
from pygit.ui.viewmodels.repository import RepositoryVM
from pygit.ui.views.repository_view import RepositoryView

if TYPE_CHECKING:
    from collections.abc import Coroutine

    from pygit.app.container import Services


class MainWindow(QMainWindow):
    """Shell principal de la aplicación."""

    def __init__(self, services: Services) -> None:
        super().__init__()
        self._services = services
        self._vm: RepositoryVM | None = None
        self._repo_view: RepositoryView | None = None
        self._tasks: set[asyncio.Task[None]] = set()

        self.setWindowTitle(f"pygit {__version__}")
        self.resize(1280, 800)
        self._build_menus()
        self._build_statusbar()

        self._stack = QStackedWidget(self)
        self._placeholder = QLabel(
            _("Open a repository to start"),
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        self._stack.addWidget(self._placeholder)
        self.setCentralWidget(self._stack)

    # --- Menus / status -----------------------------------------------------

    def _build_menus(self) -> None:
        menubar = self.menuBar()
        if menubar is None:
            return

        file_menu = menubar.addMenu(_("&File"))
        action_open = QAction(_("&Open Repository..."), self)
        action_open.setShortcut(QKeySequence("Ctrl+Shift+O"))
        action_open.setStatusTip(_("Open an existing Git repository"))
        action_open.triggered.connect(self._on_open_repository)
        file_menu.addAction(action_open)
        file_menu.addSeparator()
        action_quit = QAction(_("&Quit"), self)
        action_quit.setShortcut(QKeySequence(QKeySequence.StandardKey.Quit))
        action_quit.triggered.connect(self.close)
        file_menu.addAction(action_quit)

        menubar.addMenu(_("&Edit"))
        menubar.addMenu(_("&View"))

        repo_menu = menubar.addMenu(_("&Repository"))
        action_refresh = QAction(_("&Refresh"), self)
        action_refresh.setShortcut(QKeySequence("F5"))
        action_refresh.triggered.connect(self._on_refresh)
        repo_menu.addAction(action_refresh)

        help_menu = menubar.addMenu(_("&Help"))
        action_about = QAction(_("&About pygit"), self)
        help_menu.addAction(action_about)

    def _build_statusbar(self) -> None:
        bar = QStatusBar(self)
        self.setStatusBar(bar)
        bar.showMessage(_("Ready"))

    # --- Slots --------------------------------------------------------------

    def _on_open_repository(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            _("Open Repository"),
            "",
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks,
        )
        if not directory:
            return
        self._open_repository(Path(directory))

    def _on_refresh(self) -> None:
        if self._vm is None:
            return
        self._spawn(self._vm.refresh())

    def _open_repository(self, path: Path) -> None:
        if self._vm is not None and self._repo_view is not None:
            self._stack.removeWidget(self._repo_view)
            self._repo_view.deleteLater()
            self._vm.deleteLater()

        vm = RepositoryVM(
            engine=self._services.git_engine,
            workers=self._services.workers,
        )
        vm.error.connect(self._on_repo_error)
        vm.head_changed.connect(self._on_head_changed)
        vm.path_changed.connect(self._on_path_changed)

        view = RepositoryView(vm)
        self._stack.addWidget(view)
        self._stack.setCurrentWidget(view)

        self._vm = vm
        self._repo_view = view

        bar = self.statusBar()
        if bar is not None:
            bar.showMessage(_("Opening {path}…").format(path=str(path)))

        self._spawn(vm.open(path))

    def _spawn(self, coro: Coroutine[Any, Any, None]) -> None:
        """Crea un Task y mantiene una referencia hasta que termina.

        Sin esto, ``asyncio.ensure_future`` puede recolectarse antes de tiempo
        (RUF006). El callback retira la tarea del set al completarse.
        """
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def _on_repo_error(self, message: str) -> None:
        bar = self.statusBar()
        if bar is not None:
            bar.showMessage(_("Error: {msg}").format(msg=message), 8000)

    def _on_path_changed(self, path: object) -> None:
        if not isinstance(path, Path):
            return
        self.setWindowTitle(f"pygit {__version__} — {path}")

    def _on_head_changed(self, head: object) -> None:
        bar = self.statusBar()
        if bar is None:
            return
        if not isinstance(head, HeadInfo):
            return
        if head.is_unborn:
            bar.showMessage(_("HEAD is unborn"))
            return
        if head.is_detached:
            bar.showMessage(_("Detached HEAD at {sha}").format(sha=head.target_sha[:7]))
            return
        bar.showMessage(_("On branch {branch}").format(branch=head.branch_name or "?"))


__all__ = ["MainWindow"]
