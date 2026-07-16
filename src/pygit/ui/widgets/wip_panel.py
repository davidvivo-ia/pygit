"""Panel del Work-In-Progress (staging + commit).

Layout:

```
┌──────────────────────────────────┐
│ Unstaged                         │
│  M  src/foo.py                   │
│  A  bar/new.txt                  │
│ [Stage]   [Discard]              │
├──────────────────────────────────┤
│ Staged                           │
│  M  baz.txt                      │
│ [Unstage]                        │
├──────────────────────────────────┤
│ Title    [............]          │
│ Body     [............]          │
│ [ ] amend  [ ] sign-off          │
│ [Commit]                         │
└──────────────────────────────────┘
```

Stage/discard a nivel de archivo. Hunk-level se delega al diff (la
acción ``Stage hunk`` se añade en pulido de Fase 2).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pygit.ui.i18n import gettext as _

if TYPE_CHECKING:
    from pygit.domain.git.writer import StatusEntry


def _label(entry: StatusEntry) -> str:
    flags: list[str] = []
    if entry.is_staged:
        flags.append("S")
    if entry.is_modified:
        flags.append("M")
    if entry.is_new:
        flags.append("A")
    if entry.is_deleted:
        flags.append("D")
    if entry.is_renamed:
        flags.append("R")
    if entry.is_conflict:
        flags.append("!")
    prefix = "".join(flags).ljust(3)
    return f"{prefix}  {entry.path}"


class WipPanel(QWidget):
    stage_requested = Signal(list)  # list[str]
    unstage_requested = Signal(list)  # list[str]
    discard_requested = Signal(list)  # list[str]
    commit_requested = Signal(str, str, bool, bool)  # title, body, amend, sign_off
    ai_message_requested = Signal()  # user asked for AI-generated message

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        splitter = QSplitter()
        splitter.setOrientation(splitter.orientation().Vertical)
        layout.addWidget(splitter, 1)

        self._unstaged = QListWidget()
        self._unstaged.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._staged = QListWidget()
        self._staged.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)

        unstaged_box = QWidget()
        unstaged_layout = QVBoxLayout(unstaged_box)
        unstaged_layout.setContentsMargins(0, 0, 0, 0)
        unstaged_layout.addWidget(QLabel(_("Unstaged changes")))
        unstaged_layout.addWidget(self._unstaged, 1)
        unstaged_btns = QHBoxLayout()
        btn_stage = QPushButton(_("Stage"))
        btn_stage_all = QPushButton(_("Stage all"))
        btn_discard = QPushButton(_("Discard"))
        unstaged_btns.addWidget(btn_stage)
        unstaged_btns.addWidget(btn_stage_all)
        unstaged_btns.addWidget(btn_discard)
        unstaged_btns.addStretch(1)
        unstaged_layout.addLayout(unstaged_btns)
        splitter.addWidget(unstaged_box)

        staged_box = QWidget()
        staged_layout = QVBoxLayout(staged_box)
        staged_layout.setContentsMargins(0, 0, 0, 0)
        staged_layout.addWidget(QLabel(_("Staged changes")))
        staged_layout.addWidget(self._staged, 1)
        staged_btns = QHBoxLayout()
        btn_unstage = QPushButton(_("Unstage"))
        staged_btns.addWidget(btn_unstage)
        staged_btns.addStretch(1)
        staged_layout.addLayout(staged_btns)
        splitter.addWidget(staged_box)

        # --- Commit form ----------------------------------------------------
        form = QWidget()
        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(0, 6, 0, 0)
        self._title = QLineEdit()
        self._title.setPlaceholderText(_("Title (max 50)"))
        self._title.setMaxLength(120)
        self._title.textChanged.connect(self._on_title_changed)
        self._title_counter = QLabel("0/50")
        title_row = QHBoxLayout()
        title_row.addWidget(self._title, 1)
        title_row.addWidget(self._title_counter)
        form_layout.addLayout(title_row)

        self._body = QTextEdit()
        self._body.setPlaceholderText(_("Body — wrap at 72"))
        self._body.setFixedHeight(80)
        form_layout.addWidget(self._body)

        opts_row = QHBoxLayout()
        self._amend = QCheckBox(_("Amend"))
        self._signoff = QCheckBox(_("Sign-off"))
        opts_row.addWidget(self._amend)
        opts_row.addWidget(self._signoff)
        opts_row.addStretch(1)
        form_layout.addLayout(opts_row)

        buttons_row = QHBoxLayout()
        btn_ai = QPushButton(_("AI message"))
        btn_ai.setToolTip(_("Generate a commit message from the staged diff"))
        btn_commit = QPushButton(_("Commit"))
        buttons_row.addWidget(btn_ai)
        buttons_row.addStretch(1)
        buttons_row.addWidget(btn_commit)
        form_layout.addRow(buttons_row)
        layout.addWidget(form)

        # --- Wiring ---------------------------------------------------------
        btn_stage.clicked.connect(self._on_stage)
        btn_stage_all.clicked.connect(self._on_stage_all)
        btn_discard.clicked.connect(self._on_discard)
        btn_unstage.clicked.connect(self._on_unstage)
        btn_commit.clicked.connect(self._on_commit)
        btn_ai.clicked.connect(self.ai_message_requested.emit)

    def set_status(self, entries: list[StatusEntry]) -> None:
        self._unstaged.clear()
        self._staged.clear()
        for entry in entries:
            if entry.is_staged:
                item = QListWidgetItem(_label(entry))
                item.setData(0x0100, entry.path)
                self._staged.addItem(item)
            if entry.is_modified or entry.is_new or entry.is_deleted or entry.is_renamed:
                item = QListWidgetItem(_label(entry))
                item.setData(0x0100, entry.path)
                self._unstaged.addItem(item)

    def _selected_paths(self, widget: QListWidget) -> list[str]:
        out: list[str] = []
        for item in widget.selectedItems():
            path = item.data(0x0100)
            if isinstance(path, str):
                out.append(path)
        return out

    def _all_paths(self, widget: QListWidget) -> list[str]:
        out: list[str] = []
        for row in range(widget.count()):
            item = widget.item(row)
            if item is None:
                continue
            path = item.data(0x0100)
            if isinstance(path, str):
                out.append(path)
        return out

    def _on_stage(self) -> None:
        paths = self._selected_paths(self._unstaged)
        if paths:
            self.stage_requested.emit(paths)

    def _on_stage_all(self) -> None:
        paths = self._all_paths(self._unstaged)
        if paths:
            self.stage_requested.emit(paths)

    def _on_unstage(self) -> None:
        paths = self._selected_paths(self._staged)
        if paths:
            self.unstage_requested.emit(paths)

    def _on_discard(self) -> None:
        paths = self._selected_paths(self._unstaged)
        if paths:
            self.discard_requested.emit(paths)

    def _on_commit(self) -> None:
        title = self._title.text().strip()
        if not title:
            return
        body = self._body.toPlainText()
        self.commit_requested.emit(title, body, self._amend.isChecked(), self._signoff.isChecked())
        self._title.clear()
        self._body.clear()
        self._amend.setChecked(False)

    def _on_title_changed(self, text: str) -> None:
        n = len(text)
        self._title_counter.setText(f"{n}/50")

    def set_message(self, message: str) -> None:
        """Rellena title + body a partir de un mensaje libre (útil para IA)."""
        if not message:
            return
        head, _, body = message.strip().partition("\n\n")
        self._title.setText(head.splitlines()[0][:120])
        self._body.setPlainText(body.strip())


__all__ = ["WipPanel"]
