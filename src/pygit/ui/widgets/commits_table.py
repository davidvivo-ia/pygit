"""Tabla de commits con columna Graph.

Fase 1.2: 5 columnas — ``Graph | Summary | Author | Date | SHA``.

El layout del grafo (asignación de lanes) se calcula en un worker y llega
al modelo junto con la lista de commits, atómicamente. La columna Graph
se pinta con :class:`pygit.ui.widgets.graph_delegate.GraphDelegate`, que
sólo necesita la fila actual y la anterior para producir las conexiones.

Sobre rendimiento: la tabla usa ``QAbstractTableModel`` con scroll virtual
nativo de Qt — sólo se piden datos para las filas visibles. Para los 50k
commits del objetivo, el coste se concentra en ``assign_lanes`` (worker)
y en el pintado por scroll (≈30-50 filas a la vez). Validación de los 60
fps queda para una pasada de profiling al cierre de Fase 1.
"""

from __future__ import annotations

from enum import IntEnum
from typing import TYPE_CHECKING

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
)
from PySide6.QtWidgets import QHeaderView, QTableView

from pygit.ui.i18n import gettext as _

if TYPE_CHECKING:
    from pygit.domain.git.graph import GraphRow
    from pygit.domain.git.models import CommitSummary


ROW_HEIGHT = 24
LANE_WIDTH = 16


class Column(IntEnum):
    GRAPH = 0
    SUMMARY = 1
    AUTHOR = 2
    DATE = 3
    SHA = 4


class CommitsModel(QAbstractTableModel):
    def __init__(self) -> None:
        super().__init__()
        self._commits: list[CommitSummary] = []
        self._graph: list[GraphRow] = []
        self._max_lanes: int = 0

    def set_history(self, commits: list[CommitSummary], graph: list[GraphRow]) -> None:
        if len(commits) != len(graph):
            raise ValueError(f"history/graph length mismatch: {len(commits)} vs {len(graph)}")
        self.beginResetModel()
        self._commits = commits
        self._graph = graph
        self._max_lanes = max((len(row.lanes) for row in graph), default=0)
        self.endResetModel()

    def rowCount(  # noqa: N802 — Qt API
        self,
        parent: QModelIndex | QPersistentModelIndex = QModelIndex(),  # noqa: B008
    ) -> int:
        if parent.isValid():
            return 0
        return len(self._commits)

    def columnCount(  # noqa: N802 — Qt API
        self,
        parent: QModelIndex | QPersistentModelIndex = QModelIndex(),  # noqa: B008
    ) -> int:
        if parent.isValid():
            return 0
        return len(Column)

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object:
        if not index.isValid():
            return None
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        commit = self._commits[index.row()]
        column = Column(index.column())
        if column is Column.GRAPH:
            # El delegate dibuja todo; el texto queda vacío.
            return ""
        if column is Column.SUMMARY:
            return commit.summary
        if column is Column.AUTHOR:
            return commit.author.name
        if column is Column.DATE:
            return commit.author.when.strftime("%Y-%m-%d %H:%M")
        # Column.SHA (última rama exhaustiva).
        return commit.short_sha

    def headerData(  # noqa: N802 — Qt API
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation is Qt.Orientation.Horizontal:
            return {
                Column.GRAPH: "",
                Column.SUMMARY: _("Summary"),
                Column.AUTHOR: _("Author"),
                Column.DATE: _("Date"),
                Column.SHA: _("SHA"),
            }[Column(section)]
        return section + 1

    def commit_at(self, row: int) -> CommitSummary | None:
        if 0 <= row < len(self._commits):
            return self._commits[row]
        return None

    def graph_row(self, row: int) -> GraphRow | None:
        if 0 <= row < len(self._graph):
            return self._graph[row]
        return None

    @property
    def max_lanes(self) -> int:
        return self._max_lanes


class CommitsTable(QTableView):
    def __init__(self) -> None:
        super().__init__()
        self._model = CommitsModel()
        self.setModel(self._model)
        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.setVerticalScrollMode(QTableView.ScrollMode.ScrollPerPixel)
        self.verticalHeader().hide()
        self.verticalHeader().setDefaultSectionSize(ROW_HEIGHT)

        header = self.horizontalHeader()
        header.setSectionResizeMode(Column.GRAPH, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(Column.SUMMARY, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(Column.AUTHOR, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(Column.DATE, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(Column.SHA, QHeaderView.ResizeMode.ResizeToContents)

        self.setColumnWidth(Column.GRAPH, LANE_WIDTH * 4)

        # Import perezoso para evitar ciclos.
        from pygit.ui.themes import current_graph_palette
        from pygit.ui.widgets.graph_delegate import GraphDelegate

        self._graph_delegate = GraphDelegate(self)
        palette = current_graph_palette()
        if palette:
            self._graph_delegate.set_palette(palette)
        self.setItemDelegateForColumn(Column.GRAPH, self._graph_delegate)

    def set_history(self, commits: list[CommitSummary], graph: list[GraphRow]) -> None:
        self._model.set_history(commits, graph)
        lanes = max(self._model.max_lanes, 4)
        self.setColumnWidth(Column.GRAPH, LANE_WIDTH * lanes + LANE_WIDTH // 2)


__all__ = ["LANE_WIDTH", "ROW_HEIGHT", "Column", "CommitsModel", "CommitsTable"]
