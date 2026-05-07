"""Diálogos sencillos reutilizables (crear branch, crear tag, etc.).

Aislados aquí para que ``MainWindow`` no acumule UI auxiliar.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QPlainTextEdit,
    QWidget,
)

from pygit.ui.i18n import gettext as _


class _BaseFormDialog(QDialog):
    def __init__(self, parent: QWidget | None, title: str) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self._layout = QFormLayout(self)
        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)


class CreateBranchDialog(_BaseFormDialog):
    def __init__(self, parent: QWidget | None = None, *, default_target: str = "") -> None:
        super().__init__(parent, _("Create branch"))
        self.name_input = QLineEdit()
        self.target_input = QLineEdit(default_target)
        self.checkout_check = QCheckBox(_("Checkout after create"))
        self._layout.addRow(_("Name"), self.name_input)
        self._layout.addRow(_("Target (sha or branch, blank=HEAD)"), self.target_input)
        self._layout.addRow("", self.checkout_check)
        self._layout.addRow(self._buttons)

    def values(self) -> tuple[str, str | None, bool]:
        target = self.target_input.text().strip() or None
        return self.name_input.text().strip(), target, self.checkout_check.isChecked()


class CreateTagDialog(_BaseFormDialog):
    def __init__(self, parent: QWidget | None = None, *, default_target: str = "") -> None:
        super().__init__(parent, _("Create tag"))
        self.name_input = QLineEdit()
        self.target_input = QLineEdit(default_target)
        self.message_input = QPlainTextEdit()
        self.message_input.setPlaceholderText(_("Optional — non-empty creates an annotated tag"))
        self._layout.addRow(_("Name"), self.name_input)
        self._layout.addRow(_("Target (sha)"), self.target_input)
        self._layout.addRow(_("Message"), self.message_input)
        self._layout.addRow(self._buttons)

    def values(self) -> tuple[str, str, str]:
        return (
            self.name_input.text().strip(),
            self.target_input.text().strip(),
            self.message_input.toPlainText().strip(),
        )


class StashDialog(_BaseFormDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, _("Stash changes"))
        self.message_input = QLineEdit()
        self.untracked_check = QCheckBox(_("Include untracked"))
        self._layout.addRow(_("Message"), self.message_input)
        self._layout.addRow("", self.untracked_check)
        self._layout.addRow(self._buttons)

    def values(self) -> tuple[str, bool]:
        return self.message_input.text().strip(), self.untracked_check.isChecked()


class TextInputDialog(_BaseFormDialog):
    def __init__(
        self,
        parent: QWidget | None,
        title: str,
        label: str,
        *,
        default: str = "",
        placeholder: str = "",
    ) -> None:
        super().__init__(parent, title)
        self.input = QLineEdit(default)
        self.input.setPlaceholderText(placeholder)
        self._layout.addRow(label, self.input)
        self._layout.addRow(self._buttons)

    def value(self) -> str:
        return self.input.text().strip()


__all__ = [
    "CreateBranchDialog",
    "CreateTagDialog",
    "StashDialog",
    "TextInputDialog",
]
