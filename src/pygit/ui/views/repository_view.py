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

    def _spawn(self, coro: Coroutine[Any, Any, None]) -> None:
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)


__all__ = ["RepositoryView"]
