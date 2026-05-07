"""Wizard de primera ejecución.

Tres pasos: identidad (user.name/email), preferencias (idioma/tema) y
AI opt-in (proveedor/modelo/API key). Persiste en el ``config.toml``
del usuario via ``platformdirs`` y, si aplica, en ``~/.gitconfig`` global.
"""

from __future__ import annotations

import subprocess

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLineEdit,
    QWidget,
    QWizard,
    QWizardPage,
)

from pygit.ui.i18n import gettext as _


class _IdentityPage(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle(_("Identity"))
        self.setSubTitle(_("These values become your Git user.name/user.email."))
        self.name = QLineEdit()
        self.email = QLineEdit()
        layout = QFormLayout(self)
        layout.addRow(_("Name"), self.name)
        layout.addRow(_("Email"), self.email)
        self.registerField("name*", self.name)
        self.registerField("email*", self.email)


class _PreferencesPage(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle(_("Preferences"))
        self.language = QComboBox()
        self.language.addItem("Español", "es")
        self.language.addItem("English", "en")
        self.theme = QComboBox()
        self.theme.addItem(_("Dark"), "dark")
        self.theme.addItem(_("Light"), "light")
        layout = QFormLayout(self)
        layout.addRow(_("Language"), self.language)
        layout.addRow(_("Theme"), self.theme)


class _AiPage(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle(_("AI (opt-in)"))
        self.setSubTitle(
            _(
                "Optional. If enabled, pygit can draft commit messages and PR "
                "descriptions. Keys are stored in your OS keyring."
            )
        )
        self.enabled = QCheckBox(_("Enable AI features"))
        self.provider = QComboBox()
        self.provider.addItem("OpenAI", "openai")
        self.provider.addItem("Anthropic", "anthropic")
        self.provider.addItem("Ollama (local)", "ollama")
        self.model = QLineEdit()
        self.model.setPlaceholderText(_("Model — leave blank for default"))
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        layout = QFormLayout(self)
        layout.addRow(self.enabled)
        layout.addRow(_("Provider"), self.provider)
        layout.addRow(_("Model"), self.model)
        layout.addRow(_("API key (cloud only)"), self.api_key)


class OnboardingWizard(QWizard):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(_("Welcome to pygit"))
        self.identity = _IdentityPage()
        self.preferences = _PreferencesPage()
        self.ai = _AiPage()
        self.addPage(self.identity)
        self.addPage(self.preferences)
        self.addPage(self.ai)

    def values(self) -> dict[str, object]:
        return {
            "name": self.identity.name.text().strip(),
            "email": self.identity.email.text().strip(),
            "language": self.preferences.language.currentData(),
            "theme": self.preferences.theme.currentData(),
            "ai_enabled": self.ai.enabled.isChecked(),
            "ai_provider": self.ai.provider.currentData(),
            "ai_model": self.ai.model.text().strip(),
            "ai_api_key": self.ai.api_key.text(),
        }


def apply_git_identity(name: str, email: str) -> None:
    """Escribe ``user.name``/``user.email`` en la config global de git."""
    if not name or not email:
        return
    try:
        subprocess.run(["git", "config", "--global", "user.name", name], check=False)
        subprocess.run(["git", "config", "--global", "user.email", email], check=False)
    except FileNotFoundError:
        # git no instalado en el host — no rompemos el flujo.
        pass


__all__ = ["OnboardingWizard", "apply_git_identity"]
