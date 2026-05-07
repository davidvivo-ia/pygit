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


class CloneDialog(_BaseFormDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, _("Clone repository"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://github.com/user/repo.git")
        self.target_input = QLineEdit()
        self.target_input.setPlaceholderText(_("Local destination (folder)"))
        self._layout.addRow(_("URL"), self.url_input)
        self._layout.addRow(_("Target"), self.target_input)
        self._layout.addRow(self._buttons)

    def values(self) -> tuple[str, str]:
        return self.url_input.text().strip(), self.target_input.text().strip()


class CreatePrDialog(_BaseFormDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, _("Create Pull Request"))
        self.title_input = QLineEdit()
        self.source_input = QLineEdit()
        self.target_input = QLineEdit("main")
        self.body_input = QPlainTextEdit()
        self.body_input.setPlaceholderText(_("Description (Markdown ok)"))
        self.draft_check = QCheckBox(_("Draft"))
        self._layout.addRow(_("Title"), self.title_input)
        self._layout.addRow(_("Source branch"), self.source_input)
        self._layout.addRow(_("Target branch"), self.target_input)
        self._layout.addRow(_("Body"), self.body_input)
        self._layout.addRow("", self.draft_check)
        self._layout.addRow(self._buttons)

    def values(self) -> tuple[str, str, str, str, bool]:
        return (
            self.title_input.text().strip(),
            self.body_input.toPlainText().strip(),
            self.source_input.text().strip(),
            self.target_input.text().strip(),
            self.draft_check.isChecked(),
        )


class CredentialsDialog(_BaseFormDialog):
    def __init__(self, parent: QWidget | None = None, *, host: str = "") -> None:
        super().__init__(parent, _("Store HTTPS credentials"))
        self.host_input = QLineEdit(host)
        self.username_input = QLineEdit()
        self.token_input = QLineEdit()
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._layout.addRow(_("Host"), self.host_input)
        self._layout.addRow(_("Username"), self.username_input)
        self._layout.addRow(_("Token / password"), self.token_input)
        self._layout.addRow(self._buttons)

    def values(self) -> tuple[str, str, str]:
        return (
            self.host_input.text().strip().lower(),
            self.username_input.text().strip(),
            self.token_input.text(),
        )


class PushDialog(_BaseFormDialog):
    def __init__(self, parent: QWidget | None = None, *, default_remote: str = "origin") -> None:
        super().__init__(parent, _("Push"))
        self.remote_input = QLineEdit(default_remote)
        self.force_check = QCheckBox(_("Force-with-lease"))
        self._layout.addRow(_("Remote"), self.remote_input)
        self._layout.addRow("", self.force_check)
        self._layout.addRow(self._buttons)

    def values(self) -> tuple[str, bool]:
        return self.remote_input.text().strip(), self.force_check.isChecked()


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
    "CloneDialog",
    "CreateBranchDialog",
    "CreatePrDialog",
    "CreateTagDialog",
    "CredentialsDialog",
    "PushDialog",
    "StashDialog",
    "TextInputDialog",
]
