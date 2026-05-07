"""Pruebas mínimas de la ventana principal con pytest-qt."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from pygit import __version__
from pygit.app.container import Services
from pygit.infra.config import AppConfig
from pygit.ui.i18n import install_translations
from pygit.ui.views.main_window import MainWindow

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


@pytest.fixture(autouse=True)
def _english_translations() -> None:
    install_translations("en")


def _menu_titles(window: MainWindow) -> list[str]:
    menubar = window.menuBar()
    assert menubar is not None
    return [action.text() for action in menubar.actions() if action.text()]


def test_main_window_title_includes_version(qtbot: QtBot) -> None:
    window = MainWindow(services=Services(config=AppConfig()))
    qtbot.addWidget(window)
    assert __version__ in window.windowTitle()


def test_main_window_top_level_menus(qtbot: QtBot) -> None:
    window = MainWindow(services=Services(config=AppConfig()))
    qtbot.addWidget(window)
    titles = _menu_titles(window)
    for expected in ("&File", "&Edit", "&View", "&Repository", "&Help"):
        assert expected in titles


def test_main_window_status_ready(qtbot: QtBot) -> None:
    window = MainWindow(services=Services(config=AppConfig()))
    qtbot.addWidget(window)
    bar = window.statusBar()
    assert bar is not None
    assert bar.currentMessage() == "Ready"
