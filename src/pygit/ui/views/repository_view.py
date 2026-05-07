"""Vista de un repositorio abierto.

Layout Fase 1.3:

```
┌──────────┬────────────────────────────┐
│   Refs   │   Commits                  │
│ (tree)   ├────────────────────────────┤
│          │   Diff side-by-side        │
└──────────┴────────────────────────────┘
```

El splitter horizontal separa refs del bloque central; el splitter
vertical dentro del centro separa la tabla de commits del diff.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import QHBoxLayout, QSplitter, QWidget

from pygit.ui.widgets.commits_table import CommitsTable
from pygit.ui.widgets.diff_view import DiffView
from pygit.ui.widgets.refs_tree import RefsTree

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
        outer.setStretchFactor(0, 1)
        outer.setStretchFactor(1, 4)
        outer.setSizes([280, 1000])

        self._commits = CommitsTable()
        self._diff = DiffView()
        center.addWidget(self._commits)
        center.addWidget(self._diff)
        center.setStretchFactor(0, 3)
        center.setStretchFactor(1, 4)

        # Cableado VM ↔ widgets.
        vm.branches_changed.connect(self._refs.set_branches)
        vm.tags_changed.connect(self._refs.set_tags)
        vm.remotes_changed.connect(self._refs.set_remotes)
        vm.history_changed.connect(self._commits.set_history)
        vm.diff_changed.connect(self._on_diff_changed)

        # Click en una fila de commit dispara select_commit en la VM.
        self._commits.selectionModel().currentRowChanged.connect(self._on_commit_selected)

    def _on_commit_selected(self, current: QModelIndex, _previous: QModelIndex) -> None:
        if not current.isValid():
            return
        # Acceso al modelo: index → fila → CommitSummary
        model = self._commits.model()
        commit = getattr(model, "commit_at", lambda _r: None)(current.row())
        if commit is None:
            return
        self._spawn(self._vm.select_commit(commit.sha))

    def _on_diff_changed(self, diff: object) -> None:
        from pygit.domain.git.diff import DiffResult

        if isinstance(diff, DiffResult):
            self._diff.set_diff(diff)

    def _spawn(self, coro: Coroutine[Any, Any, None]) -> None:
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)


__all__ = ["RepositoryView"]
