"""Terminal embebida (Windows, pywinpty).

Minimalista: un ``QPlainTextEdit`` conectado a un pseudo-TTY expuesto por
``pywinpty``. El proceso hijo hereda el ``cwd`` del repositorio activo y
el ``PATH``/``env`` del proceso padre. Sin coloreado ANSI todavía (se añade
en Fase 9 con un parser dedicado).

Si ``pywinpty`` no está instalado, el widget queda deshabilitado y muestra
un placeholder explicando cómo activarlo — no rompe la app.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from PySide6.QtCore import QSocketNotifier, Signal
from PySide6.QtGui import QFont, QKeyEvent
from PySide6.QtWidgets import QPlainTextEdit

if TYPE_CHECKING:
    from pathlib import Path

try:
    import winpty  # type: ignore[import-not-found]

    _HAVE_WINPTY = True
except ImportError:  # pragma: no cover — pywinpty is Windows-only optional dep
    winpty = None  # type: ignore[assignment]
    _HAVE_WINPTY = False


class Terminal(QPlainTextEdit):
    """PTY embebido — sólo Windows por ahora."""

    exited = Signal(int)

    def __init__(self, shell: str = "cmd.exe") -> None:
        super().__init__()
        font = QFont("Cascadia Code, Consolas, monospace")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(10)
        self.setFont(font)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._pty: object | None = None
        self._notifier: QSocketNotifier | None = None
        self._shell = shell
        if not _HAVE_WINPTY:
            self.setReadOnly(True)
            self.setPlainText(
                "Terminal disabled: install pywinpty to enable the embedded terminal.\n"
            )

    def start(self, cwd: Path | None = None) -> None:
        if not _HAVE_WINPTY:
            return
        env = dict(os.environ)
        pty = winpty.PtyProcess.spawn(  # type: ignore[union-attr]
            [self._shell],
            cwd=str(cwd) if cwd else None,
            env=env,
        )
        self._pty = pty
        # winpty exposes .fd() only on POSIX; on Windows we poll via a timer.
        # Simplified: read on every keyPressEvent tick.

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 — Qt API
        if not _HAVE_WINPTY or self._pty is None:
            return
        text = event.text()
        if text:
            self._pty.write(text)  # type: ignore[attr-defined]
        # Drain output opportunistically.
        try:
            out = self._pty.read(4096, blocking=False)  # type: ignore[attr-defined]
        except Exception:
            out = ""
        if out:
            self.moveCursor(self.textCursor().MoveOperation.End)
            self.insertPlainText(out)

    def stop(self) -> None:
        import contextlib

        if self._pty is not None:
            with contextlib.suppress(Exception):
                self._pty.terminate()  # type: ignore[attr-defined]
            self._pty = None


__all__ = ["Terminal"]
