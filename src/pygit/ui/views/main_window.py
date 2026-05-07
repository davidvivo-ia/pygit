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
from pygit.domain.credentials import KeyringStore
from pygit.domain.git.advanced import RebaseAction, RebaseStep
from pygit.domain.git.models import HeadInfo
from pygit.infra.auto_fetch import AutoFetcher
from pygit.infra.config import AiConfigStored, AppConfig, UIConfig, write_config
from pygit.ui.i18n import gettext as _
from pygit.ui.viewmodels.repository import RepositoryVM
from pygit.ui.views.onboarding import OnboardingWizard, apply_git_identity
from pygit.ui.views.repository_view import RepositoryView
from pygit.ui.views.settings_dialog import SettingsDialog
from pygit.ui.widgets.command_palette import Command, CommandPalette
from pygit.ui.widgets.dialogs import (
    CloneDialog,
    CreateBranchDialog,
    CreatePrDialog,
    CreateTagDialog,
    CredentialsDialog,
    PushDialog,
    StashDialog,
    TextInputDialog,
)
from pygit.ui.widgets.rebase_editor import RebaseEditorDialog

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
        self._auto_fetcher: AutoFetcher | None = None

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
        action_clone = QAction(_("&Clone Repository..."), self)
        action_clone.triggered.connect(self._on_clone)
        file_menu.addAction(action_clone)
        action_creds = QAction(_("Store HTTPS &credentials..."), self)
        action_creds.triggered.connect(self._on_credentials)
        file_menu.addAction(action_creds)
        file_menu.addSeparator()
        action_quit = QAction(_("&Quit"), self)
        action_quit.setShortcut(QKeySequence(QKeySequence.StandardKey.Quit))
        action_quit.triggered.connect(self.close)
        file_menu.addAction(action_quit)

        edit_menu = menubar.addMenu(_("&Edit"))
        action_settings = QAction(_("&Preferences..."), self)
        action_settings.setShortcut(QKeySequence("Ctrl+,"))
        action_settings.triggered.connect(self._on_settings)
        edit_menu.addAction(action_settings)
        edit_menu.addSeparator()
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
        repo_menu.addAction(QAction(_("Interactive &Rebase..."), self, triggered=self._on_rebase))
        repo_menu.addAction(QAction(_("Show Reflog..."), self, triggered=self._on_reflog))
        repo_menu.addSeparator()
        repo_menu.addAction(QAction(_("&List Pull Requests..."), self, triggered=self._on_list_prs))
        repo_menu.addAction(QAction(_("Create &PR..."), self, triggered=self._on_create_pr))
        repo_menu.addSeparator()
        repo_menu.addAction(QAction(_("&Fetch"), self, triggered=self._on_fetch))
        repo_menu.addAction(QAction(_("&Pull"), self, triggered=self._on_pull))
        repo_menu.addAction(QAction(_("Pus&h..."), self, triggered=self._on_push))
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
        if self._auto_fetcher is not None:
            self._auto_fetcher.stop()
            self._auto_fetcher = None

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

        # Auto-fetch silencioso cada 5 min.
        async def _bg_fetch() -> None:
            if self._vm is not None:
                await self._vm.fetch(prune=True)

        self._auto_fetcher = AutoFetcher(_bg_fetch)
        self._auto_fetcher.start()

    # --- Slots: remote --------------------------------------------------------

    def _on_clone(self) -> None:
        dlg = CloneDialog(self)
        if not dlg.exec():
            return
        url, target = dlg.values()
        if not url or not target:
            return
        target_path = Path(target)

        # Clone se ejecuta en un worker pool del services.
        async def run() -> None:
            try:
                await self._services.workers.submit(_clone_helper, url, target_path)
            except Exception as exc:
                self._on_repo_error(str(exc))
                return
            self._on_info(f"cloned {url}")
            self._open_repository(target_path)

        self._spawn(run())

    def _on_credentials(self) -> None:
        dlg = CredentialsDialog(self)
        if not dlg.exec():
            return
        host, username, token = dlg.values()
        if not host or not username or not token:
            return
        try:
            KeyringStore().store(host, username, token)
        except Exception as exc:
            self._on_repo_error(f"keyring failed: {exc}")
            return
        self._on_info(f"stored credentials for {host}")

    def _on_fetch(self) -> None:
        if self._vm is not None:
            self._spawn(self._vm.fetch(prune=True))

    def _on_pull(self) -> None:
        if self._vm is not None:
            self._spawn(self._vm.pull())

    def _on_push(self) -> None:
        if self._vm is None:
            return
        dlg = PushDialog(self)
        if not dlg.exec():
            return
        remote, force = dlg.values()
        if not remote:
            return
        self._spawn(self._vm.push(remote, force=force))

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

    # --- Slots: advanced ------------------------------------------------------

    def _on_rebase(self) -> None:
        if self._vm is None:
            return

        async def run() -> None:
            history = await self._services.workers.submit(
                self._services.git_engine.walk_history,
                self._vm.path,
                limit=50,
            )
            steps = [
                RebaseStep(
                    action=RebaseAction.PICK,
                    sha=c.sha,
                    summary=c.summary,
                )
                for c in history[1:]  # skip HEAD itself
            ]
            dlg = RebaseEditorDialog(self, steps)

            def on_accept(new_steps: list[RebaseStep]) -> None:
                # We pass HEAD~N as upstream where N = len(steps).
                upstream = f"HEAD~{len(new_steps)}"
                from pygit.domain.git.advanced import run_interactive_rebase

                async def _run() -> None:
                    try:
                        from importlib import resources

                        script_path = resources.files("pygit.resources.scripts") / (
                            "rebase_sequence_editor.py"
                        )
                        await run_interactive_rebase(
                            self._services.git_cli,
                            self._vm.path,  # type: ignore[arg-type]
                            upstream,
                            new_steps,
                            sequence_editor_script=Path(str(script_path)),
                        )
                    except Exception as exc:
                        self._on_repo_error(str(exc))
                        return
                    await self._vm.refresh()

                self._spawn(_run())

            dlg.accepted_steps.connect(on_accept)
            dlg.exec()

        self._spawn(run())

    def _on_reflog(self) -> None:
        if self._vm is None:
            return

        async def run() -> None:
            entries = await self._vm.reflog(limit=200)
            from PySide6.QtWidgets import QDialog, QPlainTextEdit, QVBoxLayout

            dlg = QDialog(self)
            dlg.setWindowTitle(_("Reflog"))
            dlg.resize(720, 480)
            layout = QVBoxLayout(dlg)
            text = QPlainTextEdit(dlg)
            text.setReadOnly(True)
            lines = [f"{e.when:%Y-%m-%d %H:%M}  {e.new_sha[:7]}  {e.message}" for e in entries]
            text.setPlainText("\n".join(lines))
            layout.addWidget(text)
            dlg.exec()

        self._spawn(run())

    # --- Slots: hosting -------------------------------------------------------

    def _on_list_prs(self) -> None:
        if self._vm is None:
            return

        async def run() -> None:
            await self._vm.list_pull_requests()

        self._spawn(run())

        # Mostrar lista en un diálogo simple con PrPanel.
        from PySide6.QtWidgets import QDialog, QVBoxLayout

        from pygit.ui.widgets.pr_panel import PrPanel

        dlg = QDialog(self)
        dlg.setWindowTitle(_("Pull Requests"))
        dlg.resize(900, 480)
        layout = QVBoxLayout(dlg)
        panel = PrPanel()
        layout.addWidget(panel)

        def on_prs(items: list[object]) -> None:
            panel.set_items(items)  # type: ignore[arg-type]

        self._vm.pull_requests_changed.connect(on_prs)
        panel.refresh_requested.connect(lambda: self._spawn(self._vm.list_pull_requests()))
        panel.merge_requested.connect(lambda n: self._spawn(self._vm.merge_pull_request(n)))
        import contextlib

        dlg.exec()
        with contextlib.suppress(RuntimeError, TypeError):
            self._vm.pull_requests_changed.disconnect(on_prs)

    def _on_create_pr(self) -> None:
        if self._vm is None:
            return
        dlg = CreatePrDialog(self)
        if not dlg.exec():
            return
        title, body, source, target, draft = dlg.values()
        if not title or not source or not target:
            return
        self._spawn(self._vm.create_pull_request(title, body, source, target, draft=draft))

    # --- Slots: feedback / palette --------------------------------------------

    def _on_settings(self) -> None:
        dlg = SettingsDialog(self)
        cfg = self._services.config
        dlg.language.setCurrentIndex(0 if cfg.ui.language == "es" else 1)
        dlg.theme.setCurrentIndex(0 if cfg.ui.theme == "dark" else 1)
        dlg.ai_enabled.setChecked(cfg.ai.enabled)
        idx = max(
            0,
            ["openai", "anthropic", "ollama"].index(cfg.ai.provider)
            if cfg.ai.provider in ("openai", "anthropic", "ollama")
            else 0,
        )
        dlg.ai_provider.setCurrentIndex(idx)
        dlg.ai_model.setText(cfg.ai.model)
        if not dlg.exec():
            return
        values = dlg.values()
        new_cfg = AppConfig(
            ui=UIConfig(
                language=str(values["language"] or "es"),
                theme=str(values["theme"] or "dark"),
            ),
            ai=AiConfigStored(
                enabled=bool(values["ai_enabled"]),
                provider=str(values["ai_provider"] or "openai"),
                model=str(values["ai_model"] or ""),
            ),
        )
        write_config(new_cfg)
        if values["name"] and values["email"]:
            apply_git_identity(str(values["name"]), str(values["email"]))
        if values["ai_api_key"]:
            import keyring  # local import: only when user actually saves a key

            from pygit.domain.credentials import KEYRING_SERVICE

            keyring.set_password(
                f"{KEYRING_SERVICE}-ai", str(values["ai_provider"]), str(values["ai_api_key"])
            )
        self._on_info(_("Preferences saved. Restart to apply language/theme."))

    def maybe_run_onboarding(self) -> None:
        """Lanza el wizard si la config aún no existe en disco."""
        from pygit.infra.config import config_path

        if config_path().exists():
            return
        wiz = OnboardingWizard(self)
        if not wiz.exec():
            # User cancelled — write a minimal default config so we don't ask again.
            write_config(self._services.config)
            return
        values = wiz.values()
        new_cfg = AppConfig(
            ui=UIConfig(
                language=str(values["language"] or "es"),
                theme=str(values["theme"] or "dark"),
            ),
            ai=AiConfigStored(
                enabled=bool(values["ai_enabled"]),
                provider=str(values["ai_provider"] or "openai"),
                model=str(values["ai_model"] or ""),
            ),
        )
        write_config(new_cfg)
        apply_git_identity(str(values["name"] or ""), str(values["email"] or ""))
        if values["ai_enabled"] and values["ai_api_key"]:
            import keyring

            from pygit.domain.credentials import KEYRING_SERVICE

            keyring.set_password(
                f"{KEYRING_SERVICE}-ai", str(values["ai_provider"]), str(values["ai_api_key"])
            )

    def _on_command_palette(self) -> None:
        palette = CommandPalette(self)
        palette.set_commands(self._build_commands())
        palette.exec()

    def _build_commands(self) -> list[Command]:
        cmds: list[Command] = [
            Command(
                "file.open_repository", _("Open Repository..."), "file", self._on_open_repository
            ),
            Command("file.clone", _("Clone Repository..."), "file", self._on_clone),
            Command(
                "file.credentials",
                _("Store HTTPS credentials..."),
                "file",
                self._on_credentials,
            ),
            Command("file.quit", _("Quit"), "file", self.close),
        ]
        if self._vm is not None:
            cmds.extend(
                [
                    Command("repo.refresh", _("Refresh"), "repo", self._on_refresh),
                    Command("repo.undo", _("Undo"), "repo", self._on_undo),
                    Command("repo.redo", _("Redo"), "repo", self._on_redo),
                    Command("repo.fetch", _("Fetch"), "remote", self._on_fetch),
                    Command("repo.pull", _("Pull"), "remote", self._on_pull),
                    Command("repo.push", _("Push..."), "remote", self._on_push),
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


def _clone_helper(url: str, target: Path) -> None:
    from pygit.domain.credentials import build_default_resolver
    from pygit.domain.git.remote import clone

    clone(url, target, credentials=build_default_resolver())


__all__ = ["MainWindow"]
