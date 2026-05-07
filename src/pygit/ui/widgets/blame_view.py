"""Vista de blame: tabla con anotaciones laterales por línea.

Columnas: ``# | sha7 | autor | fecha | contenido``. La fila se selecciona
entera; click en sha7 emite ``commit_clicked(sha)`` para saltar al log.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
    Signal,
)
from PySide6.QtWidgets import QHeaderView, QTableView

from pygit.ui.i18n import gettext as _

if TYPE_CHECKING:
    from pygit.domain.git.blame import BlameLine


class _BlameModel(QAbstractTableModel):
    HEADERS = ("#", "SHA", "Author", "Date", "")

    def __init__(self) -> None:
        super().__init__()
        self._lines: list[BlameLine] = []

    def set_lines(self, lines: list[BlameLine]) -> None:
        self.beginResetModel()
        self._lines = lines
        self.endResetModel()

    def rowCount(  # noqa: N802
        self,
        parent: QModelIndex | QPersistentModelIndex = QModelIndex(),  # noqa: B008
    ) -> int:
        if parent.isValid():
            return 0
        return len(self._lines)

    def columnCount(  # noqa: N802
        self,
        parent: QModelIndex | QPersistentModelIndex = QModelIndex(),  # noqa: B008
    ) -> int:
        if parent.isValid():
            return 0
        return len(self.HEADERS)

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object:
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        line = self._lines[index.row()]
        col = index.column()
        if col == 0:
            return line.lineno
        if col == 1:
            return line.short_sha
        if col == 2:
            return line.author_name
        if col == 3:
            return line.when.strftime("%Y-%m-%d")
        if col == 4:
            return line.content
        return None

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation is Qt.Orientation.Horizontal:
            label = self.HEADERS[section]
            return _(label) if label else ""
        return section + 1


class BlameView(QTableView):
    commit_clicked = Signal(str)  # sha

    def __init__(self) -> None:
        super().__init__()
        self._model = _BlameModel()
        self.setModel(self._model)
        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.setShowGrid(False)
        self.setAlternatingRowColors(True)
        self.verticalHeader().hide()
        header = self.horizontalHeader()
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        for col in range(4):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.doubleClicked.connect(self._on_double_clicked)

    def set_blame(self, lines: list[BlameLine]) -> None:
        self._model.set_lines(lines)

    def _on_double_clicked(self, index: QModelIndex) -> None:
        if not index.isValid():
            return
        if 0 <= index.row() < len(self._model._lines):
            self.commit_clicked.emit(self._model._lines[index.row()].sha)


__all__ = ["BlameView"]
