"""Delegate Qt que pinta la columna Graph.

Toma los datos pre-calculados (:class:`pygit.domain.git.graph.GraphRow`) del
modelo y los traduce a líneas + punto. Sólo necesita la fila actual y la
anterior; ambas se leen vía :meth:`CommitsModel.graph_row`.

Estética:

- Diagonales dibujadas como curvas cúbicas de Bézier: puntos de control
  desplazados en vertical para que la línea salga vertical del dot y
  entre vertical al siguiente commit. Esto reproduce el look
  SourceGit/GitKraken sin coste apreciable (unas decenas de rows visibles).
- Verticales rectas.
- Dot circular con borde ligeramente más oscuro para dar contraste.

Paleta: paleta por defecto Catppuccin Mocha (agradable en claro y
oscuro). Puede sustituirse en runtime con :meth:`set_palette` a partir
de un tema JSON cargado desde ``pygit.ui.themes.loader``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QStyledItemDelegate

from pygit.ui.widgets.commits_table import LANE_WIDTH, CommitsModel

if TYPE_CHECKING:
    from PySide6.QtCore import QModelIndex
    from PySide6.QtWidgets import QStyleOptionViewItem


PALETTE: tuple[str, ...] = (
    "#89b4fa",  # blue
    "#a6e3a1",  # green
    "#f9e2af",  # yellow
    "#f38ba8",  # red
    "#cba6f7",  # mauve
    "#94e2d5",  # teal
    "#fab387",  # peach
    "#f5c2e7",  # pink
)

DOT_RADIUS = 4.5
LINE_WIDTH = 2.0


class GraphDelegate(QStyledItemDelegate):
    """Pinta la celda de la columna Graph con curvas cúbicas."""

    def __init__(self, parent: object = None) -> None:
        super().__init__(parent)
        self._colors: tuple[QColor, ...] = tuple(QColor(c) for c in PALETTE)

    def set_palette(self, colors: list[str]) -> None:
        if colors:
            self._colors = tuple(QColor(c) for c in colors)

    def _pen(self, color_index: int) -> QPen:
        color = self._colors[color_index % len(self._colors)]
        pen = QPen(color, LINE_WIDTH)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        return pen

    @staticmethod
    def _curve(painter: QPainter, x1: float, y1: float, x2: float, y2: float) -> None:
        """Cúbica que sale y entra vertical (paridad SourceGit/GitKraken)."""
        if x1 == x2:
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
            return
        dy = (y2 - y1) * 0.55
        path = QPainterPath(QPointF(x1, y1))
        path.cubicTo(
            QPointF(x1, y1 + dy),
            QPointF(x2, y2 - dy),
            QPointF(x2, y2),
        )
        painter.drawPath(path)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        super().paint(painter, option, index)  # fondo/selección

        model = index.model()
        if not isinstance(model, CommitsModel):
            return
        row = model.graph_row(index.row())
        if row is None:
            return
        prev = model.graph_row(index.row() - 1) if index.row() > 0 else None
        prev_lanes: tuple[int | None, ...] = prev.lanes if prev is not None else ()

        rect = option.rect
        painter.save()
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            top = float(rect.top())
            bottom = float(rect.bottom())
            mid = float(rect.center().y())

            def lane_x(lane: int) -> float:
                return float(rect.left()) + lane * LANE_WIDTH + LANE_WIDTH / 2

            x_dot = lane_x(row.lane)
            incoming = set(row.incoming)
            outgoing = set(row.outgoing)
            prev_active = {i for i, c in enumerate(prev_lanes) if c is not None}

            # --- Mitad superior: viene de prev.lanes ------------------------
            for i, color_index in enumerate(prev_lanes):
                if color_index is None:
                    continue
                painter.setPen(self._pen(color_index))
                x_top = lane_x(i)
                if i in incoming:
                    self._curve(painter, x_top, top, x_dot, mid)
                elif i < len(row.lanes) and row.lanes[i] is not None:
                    painter.drawLine(QPointF(x_top, top), QPointF(x_top, mid))
                # Otros: lane muerta arriba, no se dibuja.

            # --- Mitad inferior: sale a row.lanes ---------------------------
            for i, color_index in enumerate(row.lanes):
                if color_index is None:
                    continue
                painter.setPen(self._pen(color_index))
                x_bottom = lane_x(i)
                if i == row.lane:
                    # Propia lane continúa hacia abajo.
                    painter.drawLine(QPointF(x_dot, mid), QPointF(x_bottom, bottom))
                elif i in outgoing and i not in prev_active:
                    # Padre nuevo: curva desde el dot a su nueva columna.
                    self._curve(painter, x_dot, mid, x_bottom, bottom)
                elif i in prev_active:
                    # Lane que pasa: sigue vertical.
                    painter.drawLine(QPointF(x_bottom, mid), QPointF(x_bottom, bottom))
                elif i in outgoing:
                    # Padre existente en otra columna: curva descendente.
                    self._curve(painter, x_dot, mid, x_bottom, bottom)

            # --- Punto del commit -------------------------------------------
            dot_color = self._colors[row.color % len(self._colors)]
            painter.setBrush(dot_color)
            painter.setPen(QPen(dot_color.darker(150), 1))
            painter.drawEllipse(QPointF(x_dot, mid), DOT_RADIUS, DOT_RADIUS)
        finally:
            painter.restore()


__all__ = ["DOT_RADIUS", "LINE_WIDTH", "PALETTE", "GraphDelegate"]
