"""Delegate Qt que pinta la columna Graph.

Toma los datos pre-calculados (:class:`pygit.domain.git.graph.GraphRow`) del
modelo y los traduce a líneas + punto. Necesita la fila actual y la
anterior; ambos accesos van por :meth:`CommitsModel.graph_row`.

Convención de pintura:

- Fila partida en mitad superior (de ``top`` a ``mid``) y mitad inferior
  (de ``mid`` a ``bottom``). El punto del commit se sitúa en ``mid``.
- En la mitad superior se dibujan las líneas que vienen de la fila previa
  (``prev.lanes``):
    * Si la lane termina aquí (``i in row.incoming``): línea diagonal/recta
      desde ``(i, top)`` hasta ``(row.lane, mid)``.
    * En caso contrario, vertical pasando por ``(i, top)``→``(i, mid)``.
- En la mitad inferior se dibujan las líneas hacia la fila siguiente
  (``row.lanes``):
    * Si la lane arranca en este commit (``i in row.outgoing`` y la columna
      no estaba en ``prev.lanes``): diagonal/recta desde ``(row.lane, mid)``
      a ``(i, bottom)``.
    * Si la lane es la del commit (``i == row.lane``) y continúa: vertical
      ``(row.lane, mid)``→``(row.lane, bottom)``.
    * Si la lane existe en ``row.lanes`` y existía en ``prev.lanes``:
      vertical pasando por ``(i, mid)``→``(i, bottom)``.

Paleta determinística: el modelo entrega un ``color_index`` por lane;
aquí se mapea a un color de una paleta fija (Catppuccin Mocha por
defecto, agradable en oscuro y claro).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
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

DOT_RADIUS = 4
LINE_WIDTH = 2


class GraphDelegate(QStyledItemDelegate):
    """Pinta la celda de la columna Graph."""

    def __init__(self, parent: object = None) -> None:
        super().__init__(parent)
        self._colors = tuple(QColor(c) for c in PALETTE)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        # Fondo y selección estándar (alternating rows, hover, etc.).
        super().paint(painter, option, index)

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

            # --- Mitad superior ---------------------------------------------
            for i, color_index in enumerate(prev_lanes):
                if color_index is None:
                    continue
                pen_color = self._colors[color_index % len(self._colors)]
                pen = QPen(pen_color, LINE_WIDTH)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                x_top = lane_x(i)
                if i in incoming:
                    painter.drawLine(QPointF(x_top, top), QPointF(x_dot, mid))
                elif i < len(row.lanes) and row.lanes[i] is not None:
                    painter.drawLine(QPointF(x_top, top), QPointF(x_top, mid))
                # En cualquier otro caso, la lane existía arriba pero no abajo
                # ni absorbida: línea muerta, no se dibuja.

            # --- Mitad inferior ---------------------------------------------
            for i, color_index in enumerate(row.lanes):
                if color_index is None:
                    continue
                pen_color = self._colors[color_index % len(self._colors)]
                pen = QPen(pen_color, LINE_WIDTH)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                x_bottom = lane_x(i)
                if i == row.lane:
                    # Continuación de la propia lane hacia abajo.
                    painter.drawLine(QPointF(x_dot, mid), QPointF(x_bottom, bottom))
                elif i in outgoing and i not in prev_active:
                    # Padre nuevo que arranca de este commit.
                    painter.drawLine(QPointF(x_dot, mid), QPointF(x_bottom, bottom))
                elif i in prev_active:
                    # Lane que pasaba ya y sigue.
                    painter.drawLine(QPointF(x_bottom, mid), QPointF(x_bottom, bottom))
                elif i in outgoing:
                    # Padre que ya vivía en otra columna pero que recibe edge:
                    # se traza el edge en la mitad inferior hacia su columna
                    # destino. (Caso de la "rama lateral que vuelve".)
                    painter.drawLine(QPointF(x_dot, mid), QPointF(x_bottom, bottom))

            # --- Punto del commit -------------------------------------------
            dot_color = self._colors[row.color % len(self._colors)]
            painter.setBrush(dot_color)
            painter.setPen(QPen(dot_color.darker(140), 1))
            painter.drawEllipse(QPointF(x_dot, mid), DOT_RADIUS, DOT_RADIUS)
        finally:
            painter.restore()


__all__ = ["DOT_RADIUS", "LINE_WIDTH", "PALETTE", "GraphDelegate"]
