"""Vista de un repositorio abierto.

Layout Fase 2:

```
┌──────────┬────────────────────────────┬──────────┐
│   Refs   │   Commits                  │   WIP    │
│ (tree)   ├────────────────────────────┤ (panel)  │
│          │   Diff side-by-side        │          │
└──────────┴────────────────────────────┴──────────┘
```
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import QHBoxLayout, QSplitter, QWidget

from pygit.domain.git.writer import CommitOptions
from pygit.ui.widgets.commits_table import CommitsTable
from pygit.ui.widgets.diff_view import DiffView
from pygit.ui.widgets.refs_tree import RefsTree
from pygit.ui.widgets.wip_panel import WipPanel

if TYPE_CHECKING:
    from collections.abc import Coroutine

    from pygit.ui.viewmodels.repository import RepositoryVM


class RepositoryView(QWidget):
    def __init__(self, vm: RepositoryVM) -> None:
        super().__init__()
        self._vm = vm
        self._tasks: set[asyncio.Task[None]] = set()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        outer = QSplitter(Qt.Orientation.Horizontal, self)
        layout.addWidget(outer)

        self._refs = RefsTree()
        outer.addWidget(self._refs)

        center = QSplitter(Qt.Orientation.Vertical, outer)
        outer.addWidget(center)

        self._wip = WipPanel()
        outer.addWidget(self._wip)
        outer.setStretchFactor(0, 1)
        outer.setStretchFactor(1, 4)
        outer.setStretchFactor(2, 2)
        outer.setSizes([260, 900, 320])

        self._commits = CommitsTable()
        self._diff = DiffView()
        center.addWidget(self._commits)
        center.addWidget(self._diff)
        center.setStretchFactor(0, 3)
        center.setStretchFactor(1, 4)

        # VM → widgets
        vm.branches_changed.connect(self._refs.set_branches)
        vm.tags_changed.connect(self._refs.set_tags)
        vm.remotes_changed.connect(self._refs.set_remotes)
        vm.history_changed.connect(self._commits.set_history)
        vm.diff_changed.connect(self._on_diff_changed)
        vm.status_changed.connect(self._wip.set_status)

        # Widgets → VM
        self._commits.selectionModel().currentRowChanged.connect(self._on_commit_selected)
        self._wip.stage_requested.connect(self._on_stage)
        self._wip.unstage_requested.connect(self._on_unstage)
        self._wip.discard_requested.connect(self._on_discard)
        self._wip.commit_requested.connect(self._on_commit)
        self._wip.ai_message_requested.connect(self._on_ai_message)

    def _on_commit_selected(self, current: QModelIndex, _previous: QModelIndex) -> None:
        if not current.isValid():
            return
        model = self._commits.model()
        commit = getattr(model, "commit_at", lambda _r: None)(current.row())
        if commit is None:
            return
        self._spawn(self._vm.select_commit(commit.sha))

    def _on_diff_changed(self, diff: object) -> None:
        from pygit.domain.git.diff import DiffResult

        if isinstance(diff, DiffResult):
            self._diff.set_diff(diff)

    def _on_stage(self, paths: list[str]) -> None:
        self._spawn(self._vm.stage_paths(paths))

    def _on_unstage(self, paths: list[str]) -> None:
        self._spawn(self._vm.unstage_paths(paths))

    def _on_discard(self, paths: list[str]) -> None:
        self._spawn(self._vm.discard_paths(paths))

    def _on_commit(self, title: str, body: str, amend: bool, sign_off: bool) -> None:
        self._spawn(
            self._vm.commit(CommitOptions(summary=title, body=body, amend=amend, sign_off=sign_off))
        )

    def _on_ai_message(self) -> None:
        # Load AI config; keyring supplies the API key.
        import contextlib

        from pygit.domain.ai import AiConfig
        from pygit.domain.credentials import KEYRING_SERVICE
        from pygit.infra.config import load_config

        cfg = load_config()
        if not cfg.ai.enabled:
            return
        api_key = ""
        with contextlib.suppress(Exception):
            import keyring

            api_key = keyring.get_password(f"{KEYRING_SERVICE}-ai", cfg.ai.provider) or ""

        ai_config = AiConfig(provider=cfg.ai.provider, model=cfg.ai.model, api_key=api_key)

        async def run() -> None:
            message = await self._vm.ai_commit_message(ai_config)
            if message:
                self._wip.set_message(message)

        self._spawn(run())

    def _spawn(self, coro: Coroutine[Any, Any, None]) -> None:
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)


__all__ = ["RepositoryView"]
