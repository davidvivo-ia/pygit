"""Tabla de commits del repositorio.

Fase 1.1: tabla simple con columnas ``Summary | Author | Date | SHA``.
La columna ``Graph`` y el render lane-based se incorporan en Fase 1.2,
junto con scroll virtual sobre ``QAbstractTableModel`` para soportar
los 50k commits de paridad con SmartGit/GitKraken.
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
    from pygit.domain.git.models import CommitSummary


class Column(IntEnum):
    SUMMARY = 0
    AUTHOR = 1
    DATE = 2
    SHA = 3


class CommitsModel(QAbstractTableModel):
    def __init__(self) -> None:
        super().__init__()
        self._commits: list[CommitSummary] = []

    def set_commits(self, commits: list[CommitSummary]) -> None:
        self.beginResetModel()
        self._commits = commits
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
        if column is Column.SUMMARY:
            return commit.summary
        if column is Column.AUTHOR:
            return commit.author.name
        if column is Column.DATE:
            return commit.author.when.strftime("%Y-%m-%d %H:%M")
        if column is Column.SHA:
            return commit.short_sha
        return None

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


class CommitsTable(QTableView):
    def __init__(self) -> None:
        super().__init__()
        self._model = CommitsModel()
        self.setModel(self._model)
        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.verticalHeader().hide()
        header = self.horizontalHeader()
        header.setSectionResizeMode(Column.SUMMARY, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(Column.AUTHOR, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(Column.DATE, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(Column.SHA, QHeaderView.ResizeMode.ResizeToContents)

    def set_commits(self, commits: list[CommitSummary]) -> None:
        self._model.set_commits(commits)


__all__ = ["CommitsModel", "CommitsTable"]
