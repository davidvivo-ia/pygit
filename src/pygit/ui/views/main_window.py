"""Ventana principal.

Orquesta apertura de repos y expone el catálogo de acciones (menú,
atajos, command palette). La lógica vive en ``RepositoryVM``; aquí sólo
desencadenamos coroutines vía :meth:`_spawn`.
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
from pygit.ui.widgets.command_palette import Command, CommandPalette
from pygit.ui.widgets.dialogs import (
    CreateBranchDialog,
    CreateTagDialog,
    StashDialog,
    TextInputDialog,
)

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
        self.resize(1440, 880)
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
        action_open.triggered.connect(self._on_open_repository)
        file_menu.addAction(action_open)
        file_menu.addSeparator()
        action_quit = QAction(_("&Quit"), self)
        action_quit.setShortcut(QKeySequence(QKeySequence.StandardKey.Quit))
        action_quit.triggered.connect(self.close)
        file_menu.addAction(action_quit)

        edit_menu = menubar.addMenu(_("&Edit"))
        action_undo = QAction(_("&Undo"), self)
        action_undo.setShortcut(QKeySequence("Ctrl+Z"))
        action_undo.triggered.connect(self._on_undo)
        edit_menu.addAction(action_undo)
        action_redo = QAction(_("&Redo"), self)
        action_redo.setShortcut(QKeySequence("Ctrl+Y"))
        action_redo.triggered.connect(self._on_redo)
        edit_menu.addAction(action_redo)

        menubar.addMenu(_("&View"))

        repo_menu = menubar.addMenu(_("&Repository"))
        action_refresh = QAction(_("&Refresh"), self)
        action_refresh.setShortcut(QKeySequence("F5"))
        action_refresh.triggered.connect(self._on_refresh)
        repo_menu.addAction(action_refresh)

        repo_menu.addSeparator()
        repo_menu.addAction(QAction(_("&Create Branch..."), self, triggered=self._on_create_branch))
        repo_menu.addAction(
            QAction(_("Checkout Branch..."), self, triggered=self._on_checkout_branch)
        )
        repo_menu.addAction(QAction(_("Merge Branch..."), self, triggered=self._on_merge_branch))
        repo_menu.addSeparator()
        repo_menu.addAction(QAction(_("Create &Tag..."), self, triggered=self._on_create_tag))
        repo_menu.addAction(QAction(_("&Stash..."), self, triggered=self._on_stash))
        repo_menu.addAction(QAction(_("Stash Pop"), self, triggered=self._on_stash_pop))
        repo_menu.addSeparator()

        action_palette = QAction(_("&Command Palette..."), self)
        action_palette.setShortcut(QKeySequence("Ctrl+Shift+P"))
        action_palette.triggered.connect(self._on_command_palette)
        repo_menu.addAction(action_palette)
        # Atajo alternativo Ctrl+P (paridad VS Code).
        action_palette_alt = QAction(self)
        action_palette_alt.setShortcut(QKeySequence("Ctrl+P"))
        action_palette_alt.triggered.connect(self._on_command_palette)
        self.addAction(action_palette_alt)

        help_menu = menubar.addMenu(_("&Help"))
        action_about = QAction(_("&About pygit"), self)
        help_menu.addAction(action_about)

    def _build_statusbar(self) -> None:
        bar = QStatusBar(self)
        self.setStatusBar(bar)
        bar.showMessage(_("Ready"))

    # --- Slots: file -----------------------------------------------------------

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
        vm.info.connect(self._on_info)
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

    # --- Slots: repository actions --------------------------------------------

    def _on_undo(self) -> None:
        if self._vm is not None:
            self._spawn(self._vm.undo())

    def _on_redo(self) -> None:
        if self._vm is not None:
            self._spawn(self._vm.redo())

    def _on_create_branch(self) -> None:
        if self._vm is None:
            return
        dlg = CreateBranchDialog(self)
        if not dlg.exec():
            return
        name, target, checkout = dlg.values()
        if not name:
            return

        async def run() -> None:
            await self._vm.create_branch(name, target)
            if checkout:
                await self._vm.checkout_branch(name)

        self._spawn(run())

    def _on_checkout_branch(self) -> None:
        if self._vm is None:
            return
        dlg = TextInputDialog(self, _("Checkout"), _("Branch name"), placeholder="main")
        if not dlg.exec():
            return
        name = dlg.value()
        if not name:
            return
        self._spawn(self._vm.checkout_branch(name))

    def _on_merge_branch(self) -> None:
        if self._vm is None:
            return
        dlg = TextInputDialog(self, _("Merge"), _("Branch to merge into HEAD"))
        if not dlg.exec():
            return
        name = dlg.value()
        if not name:
            return
        self._spawn(self._vm.merge_branch(name))

    def _on_create_tag(self) -> None:
        if self._vm is None:
            return
        head = self._vm.head
        default_target = head.target_sha if head and not head.is_unborn else ""
        dlg = CreateTagDialog(self, default_target=default_target)
        if not dlg.exec():
            return
        name, target, message = dlg.values()
        if not name or not target:
            return
        self._spawn(self._vm.create_tag(name, target, message=message))

    def _on_stash(self) -> None:
        if self._vm is None:
            return
        dlg = StashDialog(self)
        if not dlg.exec():
            return
        message, untracked = dlg.values()
        self._spawn(self._vm.stash_save(message, include_untracked=untracked))

    def _on_stash_pop(self) -> None:
        if self._vm is not None:
            self._spawn(self._vm.stash_pop(0))

    # --- Slots: feedback / palette --------------------------------------------

    def _on_command_palette(self) -> None:
        palette = CommandPalette(self)
        palette.set_commands(self._build_commands())
        palette.exec()

    def _build_commands(self) -> list[Command]:
        cmds: list[Command] = [
            Command(
                "file.open_repository", _("Open Repository..."), "file", self._on_open_repository
            ),
            Command("file.quit", _("Quit"), "file", self.close),
        ]
        if self._vm is not None:
            cmds.extend(
                [
                    Command("repo.refresh", _("Refresh"), "repo", self._on_refresh),
                    Command("repo.undo", _("Undo"), "repo", self._on_undo),
                    Command("repo.redo", _("Redo"), "repo", self._on_redo),
                    Command(
                        "branch.create", _("Create Branch..."), "branch", self._on_create_branch
                    ),
                    Command(
                        "branch.checkout",
                        _("Checkout Branch..."),
                        "branch",
                        self._on_checkout_branch,
                    ),
                    Command("branch.merge", _("Merge Branch..."), "branch", self._on_merge_branch),
                    Command("tag.create", _("Create Tag..."), "tag", self._on_create_tag),
                    Command("stash.save", _("Stash..."), "stash", self._on_stash),
                    Command("stash.pop", _("Stash Pop"), "stash", self._on_stash_pop),
                ]
            )
        return cmds

    def _on_repo_error(self, message: str) -> None:
        bar = self.statusBar()
        if bar is not None:
            bar.showMessage(_("Error: {msg}").format(msg=message), 8000)

    def _on_info(self, message: str) -> None:
        bar = self.statusBar()
        if bar is not None:
            bar.showMessage(message, 4000)

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

    # --- async plumbing --------------------------------------------------------

    def _spawn(self, coro: Coroutine[Any, Any, None]) -> None:
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)


__all__ = ["MainWindow"]
