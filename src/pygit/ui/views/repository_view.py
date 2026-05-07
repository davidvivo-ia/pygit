"""Vista de un repositorio abierto.

Layout Fase 1.1: ``QSplitter`` horizontal con ``RefsTree`` a la izquierda
y ``CommitsTable`` a la derecha. El panel inferior con detalles de commit
y el árbol de archivos llegan en Fase 1.3.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QSplitter, QWidget

from pygit.ui.widgets.commits_table import CommitsTable
from pygit.ui.widgets.refs_tree import RefsTree

if TYPE_CHECKING:
    from pygit.ui.viewmodels.repository import RepositoryVM


class RepositoryView(QWidget):
    def __init__(self, vm: RepositoryVM) -> None:
        super().__init__()
        self._vm = vm

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        layout.addWidget(splitter)

        self._refs = RefsTree()
        self._commits = CommitsTable()
        splitter.addWidget(self._refs)
        splitter.addWidget(self._commits)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        splitter.setSizes([280, 1000])

        vm.branches_changed.connect(self._refs.set_branches)
        vm.tags_changed.connect(self._refs.set_tags)
        vm.remotes_changed.connect(self._refs.set_remotes)
        vm.history_changed.connect(self._commits.set_commits)


__all__ = ["RepositoryView"]
