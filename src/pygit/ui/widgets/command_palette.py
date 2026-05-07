"""Command Palette (Ctrl+P).

Diálogo modal con un ``QLineEdit`` y una ``QListView``; al teclear se
filtran las acciones registradas con un fuzzy-match simple (subsecuencia
case-insensitive). ``Enter`` ejecuta la acción seleccionada.

Las acciones se registran de forma global vía :func:`register_command` —
un módulo con tres slots básicos: ``id``, ``title``, ``callback``. La
categoría es libre (``"file"``, ``"branch"``, ``"git"``…).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
    Signal,
)
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QLineEdit,
    QListView,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass(slots=True)
class Command:
    id: str
    title: str
    category: str
    callback: Callable[[], None]


def fuzzy_score(needle: str, haystack: str) -> int | None:
    """Devuelve un score (mayor = mejor) si ``needle`` es subsecuencia de
    ``haystack`` (case-insensitive). ``None`` si no matchea.
    """
    if not needle:
        return 0
    n = needle.lower()
    h = haystack.lower()
    score = 0
    last = -1
    for ch in n:
        idx = h.find(ch, last + 1)
        if idx == -1:
            return None
        # Mejor cuanto más cerca del anterior y cuanto más al principio.
        score += 100 - (idx - last - 1)
        if idx == 0 or h[idx - 1] in (" ", "/", "_", "-", "."):
            score += 50  # boost: word boundary
        last = idx
    return score


class _CommandModel(QAbstractListModel):
    def __init__(self) -> None:
        super().__init__()
        self._items: list[Command] = []

    def set_items(self, items: list[Command]) -> None:
        self.beginResetModel()
        self._items = items
        self.endResetModel()

    def item(self, row: int) -> Command | None:
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

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object:
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        cmd = self._items[index.row()]
        return f"[{cmd.category}] {cmd.title}"


class CommandPalette(QDialog):
    triggered = Signal(str)  # command id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setModal(True)
        self.setWindowTitle("")
        self.setMinimumSize(560, 320)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self._all: list[Command] = []
        self._model = _CommandModel()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self._search = QLineEdit(self)
        self._search.setPlaceholderText("Type a command…")
        self._search.textChanged.connect(self._on_filter)
        layout.addWidget(self._search)

        self._list = QListView(self)
        self._list.setModel(self._model)
        self._list.setEditTriggers(QListView.EditTrigger.NoEditTriggers)
        self._list.setSelectionMode(QListView.SelectionMode.SingleSelection)
        self._list.activated.connect(self._on_activated)
        layout.addWidget(self._list, 1)

        # Atajos: Esc cierra, Enter ejecuta selección actual.
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self.reject)
        QShortcut(QKeySequence(Qt.Key.Key_Return), self, self._activate_current)
        QShortcut(QKeySequence(Qt.Key.Key_Enter), self, self._activate_current)
        QShortcut(QKeySequence(Qt.Key.Key_Down), self, self._move_down)
        QShortcut(QKeySequence(Qt.Key.Key_Up), self, self._move_up)

    def set_commands(self, commands: list[Command]) -> None:
        self._all = list(commands)
        self._on_filter("")

    def _on_filter(self, text: str) -> None:
        if not text:
            self._model.set_items(self._all)
        else:
            scored = [
                (score, c) for c in self._all if (score := fuzzy_score(text, c.title)) is not None
            ]
            scored.sort(key=lambda it: -it[0])
            self._model.set_items([c for _, c in scored])
        # seleccionar primera fila si hay resultados
        if self._model.rowCount() > 0:
            self._list.setCurrentIndex(self._model.index(0, 0))

    def _activate_current(self) -> None:
        idx = self._list.currentIndex()
        if idx.isValid():
            self._on_activated(idx)

    def _on_activated(self, index: QModelIndex) -> None:
        cmd = self._model.item(index.row())
        if cmd is None:
            return
        self.triggered.emit(cmd.id)
        try:
            cmd.callback()
        finally:
            self.accept()

    def _move_down(self) -> None:
        cur = self._list.currentIndex().row()
        nxt = min(cur + 1, self._model.rowCount() - 1)
        self._list.setCurrentIndex(self._model.index(nxt, 0))

    def _move_up(self) -> None:
        cur = self._list.currentIndex().row()
        prv = max(cur - 1, 0)
        self._list.setCurrentIndex(self._model.index(prv, 0))


__all__ = ["Command", "CommandPalette", "fuzzy_score"]
