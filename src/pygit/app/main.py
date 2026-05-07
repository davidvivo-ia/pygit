"""Entry point de la aplicación.

Crea el ``QApplication``, integra el loop ``asyncio`` con Qt vía ``qasync``,
arranca el bootstrap, muestra splash y abre la ventana principal.

El loop asyncio se cierra ordenadamente al cerrar la última ventana — clave
para evitar ``RuntimeError: Event loop is closed`` en pruebas y CI.
"""

from __future__ import annotations

import asyncio
import sys

import qasync
from PySide6.QtWidgets import QApplication

from pygit.app.bootstrap import bootstrap
from pygit.ui.views.main_window import MainWindow
from pygit.ui.views.splash import show_splash


def main(argv: list[str] | None = None) -> int:
    args: list[str] = list(argv) if argv is not None else sys.argv
    app = QApplication.instance() or QApplication(args)
    assert isinstance(app, QApplication)
    app.setApplicationName("pygit")
    app.setOrganizationName("pygit")
    app.setApplicationDisplayName("pygit")

    splash = show_splash(app)

    services = bootstrap(app)

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = MainWindow(services=services)
    window.show()
    splash.finish(window)
    window.maybe_run_onboarding()

    with loop:
        loop.run_forever()
    return 0
