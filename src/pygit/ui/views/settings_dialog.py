"""Diálogo de Preferencias.

Pestañas:

- General: idioma, tema.
- Identity: ``user.name`` / ``user.email`` (escritos al ``--global``
  config de git).
- AI: provider/model/api_key, almacenadas en el llavero.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from pygit.ui.i18n import gettext as _


class SettingsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(_("Preferences"))
        self.setModal(True)
        self.resize(500, 380)

        layout = QVBoxLayout(self)
        tabs = QTabWidget()

        # General
        general = QWidget()
        gen_layout = QFormLayout(general)
        self.language = QComboBox()
        self.language.addItem("Español", "es")
        self.language.addItem("English", "en")
        self.theme = QComboBox()
        self.theme.addItem(_("Dark"), "dark")
        self.theme.addItem(_("Light"), "light")
        gen_layout.addRow(_("Language"), self.language)
        gen_layout.addRow(_("Theme"), self.theme)
        tabs.addTab(general, _("General"))

        # Identity
        identity = QWidget()
        id_layout = QFormLayout(identity)
        self.name = QLineEdit()
        self.email = QLineEdit()
        id_layout.addRow(_("Name"), self.name)
        id_layout.addRow(_("Email"), self.email)
        tabs.addTab(identity, _("Identity"))

        # AI
        ai = QWidget()
        ai_layout = QFormLayout(ai)
        self.ai_enabled = QCheckBox(_("Enable AI features"))
        self.ai_provider = QComboBox()
        self.ai_provider.addItem("OpenAI", "openai")
        self.ai_provider.addItem("Anthropic", "anthropic")
        self.ai_provider.addItem("Ollama (local)", "ollama")
        self.ai_model = QLineEdit()
        self.ai_api_key = QLineEdit()
        self.ai_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        ai_layout.addRow(self.ai_enabled)
        ai_layout.addRow(_("Provider"), self.ai_provider)
        ai_layout.addRow(_("Model"), self.ai_model)
        ai_layout.addRow(_("API key"), self.ai_api_key)
        tabs.addTab(ai, _("AI"))

        layout.addWidget(tabs, 1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> dict[str, object]:
        return {
            "language": self.language.currentData(),
            "theme": self.theme.currentData(),
            "name": self.name.text().strip(),
            "email": self.email.text().strip(),
            "ai_enabled": self.ai_enabled.isChecked(),
            "ai_provider": self.ai_provider.currentData(),
            "ai_model": self.ai_model.text().strip(),
            "ai_api_key": self.ai_api_key.text(),
        }


__all__ = ["SettingsDialog"]
