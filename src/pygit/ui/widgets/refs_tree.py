"""Árbol lateral con branches (locales/remotos), tags y remotes.

Implementación mínima de Fase 1.1: ``QStandardItemModel`` agrupado por
categorías. La filtración fuzzy y el drag-and-drop entre branches llegan en
fases posteriores (5.5 y 5.33).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QTreeView

from pygit.ui.i18n import gettext as _

if TYPE_CHECKING:
    from pygit.domain.git.models import BranchRef, RemoteRef, TagRef


class RefsTree(QTreeView):
    """Listado jerárquico de referencias del repositorio."""

    def __init__(self) -> None:
        super().__init__()
        self._model = QStandardItemModel(self)
        self._model.setHorizontalHeaderLabels([_("References")])
        self.setModel(self._model)
        self.setHeaderHidden(False)
        self.setUniformRowHeights(True)

    def _section(self, label: str) -> QStandardItem:
        item = QStandardItem(label)
        item.setEditable(False)
        item.setSelectable(False)
        return item

    def set_branches(self, branches: list[BranchRef]) -> None:
        self._populate_branches(branches)

    def set_tags(self, tags: list[TagRef]) -> None:
        self._populate_tags(tags)

    def set_remotes(self, remotes: list[RemoteRef]) -> None:
        self._populate_remotes(remotes)

    def clear_all(self) -> None:
        self._model.removeRows(0, self._model.rowCount())

    # --- Internals ----------------------------------------------------------

    def _ensure_section(self, key: str, label: str) -> QStandardItem:
        for row in range(self._model.rowCount()):
            item = self._model.item(row)
            if item is not None and item.data() == key:
                item.removeRows(0, item.rowCount())
                item.setText(label)
                return item
        section = self._section(label)
        section.setData(key)
        self._model.appendRow(section)
        return section

    def _populate_branches(self, branches: list[BranchRef]) -> None:
        local = [b for b in branches if not b.is_remote]
        remote = [b for b in branches if b.is_remote]
        local_section = self._ensure_section(
            "branches.local", _("Local branches ({n})").format(n=len(local))
        )
        for branch in sorted(local, key=lambda b: b.name):
            text = branch.name
            if branch.upstream:
                text = f"{branch.name}  →  {branch.upstream}"
            child = QStandardItem(text)
            child.setEditable(False)
            child.setData(branch.full_name)
            local_section.appendRow(child)

        remote_section = self._ensure_section(
            "branches.remote", _("Remote branches ({n})").format(n=len(remote))
        )
        for branch in sorted(remote, key=lambda b: b.name):
            child = QStandardItem(branch.name)
            child.setEditable(False)
            child.setData(branch.full_name)
            remote_section.appendRow(child)

    def _populate_tags(self, tags: list[TagRef]) -> None:
        section = self._ensure_section("tags", _("Tags ({n})").format(n=len(tags)))
        for tag in sorted(tags, key=lambda t: t.name):
            text = tag.name if not tag.is_annotated else f"{tag.name}  ✻"
            child = QStandardItem(text)
            child.setEditable(False)
            child.setData(tag.full_name)
            section.appendRow(child)

    def _populate_remotes(self, remotes: list[RemoteRef]) -> None:
        section = self._ensure_section("remotes", _("Remotes ({n})").format(n=len(remotes)))
        for remote in sorted(remotes, key=lambda r: r.name):
            child = QStandardItem(f"{remote.name}  ({remote.fetch_url})")
            child.setEditable(False)
            child.setData(remote.name)
            section.appendRow(child)


__all__ = ["RefsTree"]
