"""Panel ligero para Pull Requests.

Listado en una QTableView (número, autor, título, ramas) + botón
"Create PR…" + botón "Merge". Sólo se cabea cuando hay un provider
detectado y autenticado; en caso contrario muestra un placeholder.
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
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from pygit.ui.i18n import gettext as _

if TYPE_CHECKING:
    from pygit.domain.hosting import PullRequest


class _PrModel(QAbstractTableModel):
    HEADERS = ("#", "Title", "Author", "From", "Into", "State")

    def __init__(self) -> None:
        super().__init__()
        self._items: list[PullRequest] = []

    def set_items(self, items: list[PullRequest]) -> None:
        self.beginResetModel()
        self._items = items
        self.endResetModel()

    def item(self, row: int) -> PullRequest | None:
        if 0 <= row < len(self._items):
            return self._items[row]
        return None

    def rowCount(  # noqa: N802
        self,
        parent: QModelIndex | QPersistentModelIndex = QModelIndex(),  # noqa: B008
    ) -> int:
        if parent.isValid():
            return 0
        return len(self._items)

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
        pr = self._items[index.row()]
        col = index.column()
        if col == 0:
            return pr.number
        if col == 1:
            return pr.title
        if col == 2:
            return pr.author
        if col == 3:
            return pr.source_branch
        if col == 4:
            return pr.target_branch
        if col == 5:
            return pr.state + (" (draft)" if pr.is_draft else "")
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
            return _(self.HEADERS[section])
        return section + 1


class PrPanel(QWidget):
    refresh_requested = Signal()
    create_requested = Signal()
    merge_requested = Signal(int)  # PR number

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        header = QHBoxLayout()
        header.addWidget(QLabel(_("Pull Requests")))
        header.addStretch(1)
        btn_refresh = QPushButton(_("Refresh"))
        btn_create = QPushButton(_("Create..."))
        btn_merge = QPushButton(_("Merge selected"))
        header.addWidget(btn_refresh)
        header.addWidget(btn_create)
        header.addWidget(btn_merge)
        layout.addLayout(header)

        self._table = QTableView()
        self._model = _PrModel()
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().hide()
        h = self._table.horizontalHeader()
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for col in (0, 2, 3, 4, 5):
            h.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self._table, 1)

        btn_refresh.clicked.connect(self.refresh_requested.emit)
        btn_create.clicked.connect(self.create_requested.emit)
        btn_merge.clicked.connect(self._on_merge)

    def set_items(self, items: list[PullRequest]) -> None:
        self._model.set_items(items)

    def selected(self) -> PullRequest | None:
        idx = self._table.currentIndex()
        if not idx.isValid():
            return None
        return self._model.item(idx.row())

    def _on_merge(self) -> None:
        pr = self.selected()
        if pr is None:
            return
        self.merge_requested.emit(pr.number)


__all__ = ["PrPanel"]
