"""Vista de diff side-by-side.

Dos paneles ``QPlainTextEdit`` con scroll vertical sincronizado y resaltado
por línea (verde añadido, rojo borrado, neutro contexto). La construcción
de los lados se hace alineando ``-``/``+`` en pares: para cada hunk
se emparejan deletions con additions consecutivas; las que sobran se
rellenan con líneas vacías para que el side-by-side cuadre vertical.

Modos contemplados (sólo *side-by-side* en Fase 1.3, los demás llegan en
pulido):

- *side-by-side*: dos columnas.
- *unified*: una columna con prefijo ``+/-/`` (no implementado todavía).
- *swipe*: animación entre antes/después (futuro).
- *blend*: superposición translúcida (futuro).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QTextCursor
from PySide6.QtWidgets import (
    QLabel,
    QPlainTextEdit,
    QScrollBar,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from pygit.domain.git.diff import DiffResult, FileDiff, Hunk, LineOrigin

ADDITION_BG = QColor("#16331a")
DELETION_BG = QColor("#3a1e23")
HEADER_BG = QColor("#1f2233")
CONTEXT_BG = QColor("#1e1e2e")


class _DiffPane(QPlainTextEdit):
    def __init__(self) -> None:
        super().__init__()
        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        font = QFont("Cascadia Code, JetBrains Mono, Consolas, monospace")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(10)
        self.setFont(font)
        self.setTabStopDistance(4 * self.fontMetrics().horizontalAdvance(" "))


def _pair_hunk_lines(hunk: Hunk) -> list[tuple[str | None, str | None]]:
    """Empareja deletions (-) con additions (+) por orden secuencial."""
    pairs: list[tuple[str | None, str | None]] = []
    pending_minus: list[str] = []
    pending_plus: list[str] = []

    def flush() -> None:
        n = max(len(pending_minus), len(pending_plus))
        for i in range(n):
            left = pending_minus[i] if i < len(pending_minus) else None
            right = pending_plus[i] if i < len(pending_plus) else None
            pairs.append((left, right))
        pending_minus.clear()
        pending_plus.clear()

    for line in hunk.lines:
        if line.origin is LineOrigin.DELETION:
            pending_minus.append(line.content)
        elif line.origin is LineOrigin.ADDITION:
            pending_plus.append(line.content)
        else:
            flush()
            pairs.append((line.content, line.content))
    flush()
    return pairs


def _append_line(pane: _DiffPane, text: str, color: QColor | None) -> None:
    cursor = pane.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    if color is not None:
        block_format = cursor.blockFormat()
        block_format.setBackground(color)
        cursor.setBlockFormat(block_format)
    cursor.insertText(text + "\n")
    pane.setTextCursor(cursor)


class DiffView(QWidget):
    """Vista side-by-side. Llamar :meth:`set_diff` con ``DiffResult``."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._header = QLabel("")
        self._header.setObjectName("DiffHeader")
        self._header.setMargin(6)
        layout.addWidget(self._header)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self._left = _DiffPane()
        self._right = _DiffPane()
        splitter.addWidget(self._left)
        splitter.addWidget(self._right)
        splitter.setHandleWidth(2)
        layout.addWidget(splitter, 1)

        self._sync_scrollbars(self._left.verticalScrollBar(), self._right.verticalScrollBar())
        self._sync_scrollbars(self._right.verticalScrollBar(), self._left.verticalScrollBar())

    def _sync_scrollbars(self, source: QScrollBar, target: QScrollBar) -> None:
        def _on_value_changed(value: int) -> None:
            if target.value() != value:
                target.setValue(value)

        source.valueChanged.connect(_on_value_changed)

    def clear(self) -> None:
        self._left.clear()
        self._right.clear()
        self._header.setText("")

    def set_diff(self, diff: DiffResult) -> None:
        self._left.clear()
        self._right.clear()

        if not diff.files:
            self._header.setText("(no changes)")
            return

        plus = diff.total_additions
        minus = diff.total_deletions
        self._header.setText(f"{len(diff.files)} files changed · +{plus} -{minus}")

        for file in diff.files:
            self._render_file(file)

    def _render_file(self, file: FileDiff) -> None:
        path_left = file.old_path or "/dev/null"
        path_right = file.new_path or "/dev/null"
        _append_line(self._left, f"--- {path_left} [{file.status.value}]", HEADER_BG)
        _append_line(self._right, f"+++ {path_right} [{file.status.value}]", HEADER_BG)
        if file.is_binary:
            _append_line(self._left, "(binary)", HEADER_BG)
            _append_line(self._right, "(binary)", HEADER_BG)
            return
        for hunk in file.hunks:
            _append_line(self._left, hunk.header, HEADER_BG)
            _append_line(self._right, hunk.header, HEADER_BG)
            for left, right in _pair_hunk_lines(hunk):
                left_text = left if left is not None else ""
                right_text = right if right is not None else ""
                left_bg = (
                    DELETION_BG
                    if left is not None and (right is None or right != left)
                    else CONTEXT_BG
                )
                right_bg = (
                    ADDITION_BG
                    if right is not None and (left is None or left != right)
                    else CONTEXT_BG
                )
                _append_line(self._left, left_text, left_bg)
                _append_line(self._right, right_text, right_bg)


__all__ = ["DiffView"]
