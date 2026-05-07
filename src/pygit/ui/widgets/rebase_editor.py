"""Editor visual para rebase interactivo.

``QListWidget`` con drag-and-drop interno (reordena commits) más una
columna para la acción (combo: pick/reword/edit/squash/fixup/drop).
Atajos: P/R/E/S/F/D fijan la acción de la fila seleccionada (paridad
GitKraken/GitLens).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pygit.domain.git.advanced import RebaseAction, RebaseStep
from pygit.ui.i18n import gettext as _

if TYPE_CHECKING:
    from PySide6.QtGui import QKeyEvent

_ACTIONS = list(RebaseAction)
_HOTKEYS = {
    Qt.Key.Key_P: RebaseAction.PICK,
    Qt.Key.Key_R: RebaseAction.REWORD,
    Qt.Key.Key_E: RebaseAction.EDIT,
    Qt.Key.Key_S: RebaseAction.SQUASH,
    Qt.Key.Key_F: RebaseAction.FIXUP,
    Qt.Key.Key_D: RebaseAction.DROP,
}


class _StepRow(QWidget):
    def __init__(self, step: RebaseStep) -> None:
        super().__init__()
        self.sha = step.sha
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        self.combo = QComboBox()
        for action in _ACTIONS:
            self.combo.addItem(action.value, action)
        self.combo.setCurrentIndex(_ACTIONS.index(step.action))
        layout.addWidget(self.combo)
        self.label = QLabel(f"{step.sha[:7]}  {step.summary}")
        layout.addWidget(self.label, 1)

    def to_step(self) -> RebaseStep:
        action = self.combo.currentData()
        if not isinstance(action, RebaseAction):
            action = RebaseAction.PICK
        summary = self.label.text().split(" ", 1)[1] if " " in self.label.text() else ""
        return RebaseStep(action=action, sha=self.sha, summary=summary)


class RebaseEditorDialog(QDialog):
    accepted_steps = Signal(list)

    def __init__(self, parent: QWidget | None, steps: list[RebaseStep]) -> None:
        super().__init__(parent)
        self.setWindowTitle(_("Interactive rebase"))
        self.setModal(True)
        self.resize(720, 480)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(_("Reorder rows with drag-and-drop. P/R/E/S/F/D set the action.")))

        self._list = QListWidget(self)
        self._list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        layout.addWidget(self._list, 1)

        for step in steps:
            row = _StepRow(step)
            item = QListWidgetItem()
            item.setSizeHint(row.sizeHint())
            self._list.addItem(item)
            self._list.setItemWidget(item, row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 — Qt API
        action = _HOTKEYS.get(Qt.Key(event.key()))
        if action is not None:
            current = self._list.currentItem()
            if current is None:
                return
            row = self._list.itemWidget(current)
            if isinstance(row, _StepRow):
                row.combo.setCurrentIndex(_ACTIONS.index(action))
            return
        super().keyPressEvent(event)

    def _on_accept(self) -> None:
        out: list[RebaseStep] = []
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item is None:
                continue
            row = self._list.itemWidget(item)
            if isinstance(row, _StepRow):
                out.append(row.to_step())
        self.accepted_steps.emit(out)
        self.accept()


__all__ = ["RebaseEditorDialog"]
