"""Layout en carriles (lanes) del DAG de commits.

Algoritmo headless (sin Qt). Toma una lista de :class:`CommitSummary` en
orden de walker topológico+cronológico (hijo antes que padre, como devuelve
``pygit2.walk(GIT_SORT_TOPOLOGICAL | GIT_SORT_TIME)``) y produce una lista
paralela de :class:`GraphRow` lista para renderizar.

Modelo mental:

- Una lane es una columna vertical del grafo.
- Cada lane "espera" la próxima sha que la atravesará (su contenido en
  ``active``). ``None`` significa lane libre.
- Cuando un commit aparece, se buscan las lanes que esperan su sha
  (``incoming``); el commit se dibuja en la primera de ellas, y las demás
  quedan absorbidas (vacías).
- Para cada padre del commit, si ya existe otra lane esperando ese sha,
  se reutiliza esa lane (la línea sale del punto y converge hacia la lane
  existente). Si no, se intenta colocar el padre en la lane del commit
  (manteniéndola viva); si esa lane ya fue reclamada por un padre previo,
  se asigna una lane nueva. Las lanes vacías se reusan antes de extender
  el array — esto da el efecto de "una rama termina, otra arranca en la
  misma columna" típico de SourceGit.
- Los colores son persistentes por *índice* de lane: una vez que la lane 3
  recibe color 3, lo conserva incluso si se libera y reasigna. Es la
  convención de SourceGit/git-graph y produce gráficos estables.

La salida por commit (:class:`GraphRow`) trae lo justo para que un painter
dibuje la celda mirando sólo la fila actual y la anterior:

- ``lane`` y ``color``: punto del commit.
- ``lanes``: snapshot del estado *después* del commit (color por columna).
- ``incoming``: índices de columnas (de la fila anterior) que terminan
  en este commit (líneas que entran al punto).
- ``outgoing``: índices de columnas (de la fila actual) hacia las que
  parte una línea desde este commit (incluye la propia lane si continúa).

Complejidad: ``O(N · L)`` donde ``L`` es el ancho máximo simultáneo de
lanes (típicamente <30 incluso en repos grandes). Suficiente para 50k
commits ejecutándose en un worker.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pygit.domain.git.models import CommitSummary


@dataclass(slots=True, frozen=True)
class GraphRow:
    """Layout precalculado para una fila del grafo."""

    sha: str
    lane: int
    color: int
    lanes: tuple[int | None, ...]
    incoming: tuple[int, ...]
    outgoing: tuple[int, ...]


def _allocate_free_lane(
    active: list[str | None],
    colors: list[int],
    next_color: int,
    *,
    cooldown: set[int] | None = None,
) -> tuple[int, int]:
    """Devuelve ``(lane_index, next_color)`` reutilizando hueco o extendiendo.

    Si ``cooldown`` se proporciona, se saltan las lanes cuyo índice está en el
    conjunto: son lanes que quedaron libres en la fila inmediatamente anterior
    y que reutilizarlas produciría una unión visual engañosa entre historias
    desconectadas (ver ``test_two_independent_roots_get_distinct_lanes``).
    """
    for i, slot in enumerate(active):
        if slot is None and (cooldown is None or i not in cooldown):
            return i, next_color
    active.append(None)
    colors.append(next_color)
    return len(active) - 1, next_color + 1


def assign_lanes(commits: list[CommitSummary]) -> list[GraphRow]:
    """Asigna lanes y produce :class:`GraphRow` para cada commit."""
    active: list[str | None] = []
    colors: list[int] = []
    next_color = 0
    rows: list[GraphRow] = []
    # Cooldown: lanes vacías tras la fila previa. Nunca reasignamos una lane
    # que esté en cooldown a un commit "nuevo" (root sin incoming). Esto
    # impide que dos historias desconectadas queden apiladas visualmente en
    # la misma columna. El cooldown se limpia sólo cuando una lane pasa por
    # ``incoming`` — es decir, cuando su sha esperada aparece — lo que
    # garantiza continuidad estructural.
    cooldown: set[int] = set()

    for commit in commits:
        # Lanes que esperaban este commit (sha exacta).
        incoming = tuple(i for i, sha in enumerate(active) if sha == commit.sha)

        if incoming:
            my_lane = incoming[0]
            for absorbed in incoming[1:]:
                active[absorbed] = None
        else:
            my_lane, next_color = _allocate_free_lane(active, colors, next_color, cooldown=cooldown)

        my_color = colors[my_lane]

        # Distribución de padres.
        outgoing: list[int] = []
        used_lanes: set[int] = set()

        for parent_sha in commit.parents:
            existing = next((i for i, sha in enumerate(active) if sha == parent_sha), None)
            if existing is not None and existing != my_lane:
                # Otro lane ya espera este padre: convergemos hacia él.
                if existing not in used_lanes:
                    outgoing.append(existing)
                    used_lanes.add(existing)
                continue

            if my_lane not in used_lanes:
                target = my_lane
            else:
                target, next_color = _allocate_free_lane(
                    active, colors, next_color, cooldown=cooldown
                )
            active[target] = parent_sha
            if target not in used_lanes:
                outgoing.append(target)
                used_lanes.add(target)

        if my_lane not in used_lanes:
            # Nadie reclamó la lane del commit (root, o todos los padres ya
            # vivían en otras lanes): liberamos.
            active[my_lane] = None

        lanes_snapshot = tuple(
            colors[i] if active[i] is not None else None for i in range(len(active))
        )

        rows.append(
            GraphRow(
                sha=commit.sha,
                lane=my_lane,
                color=my_color,
                lanes=lanes_snapshot,
                incoming=incoming,
                outgoing=tuple(outgoing),
            )
        )

        # Cooldown para la siguiente iteración: cualquier lane vacía tras esta
        # fila. Una lane sale del cooldown cuando un commit la reclama vía
        # ``incoming`` (matching de sha), lo que ocurre por definición cuando
        # forma parte de una cadena de padres.
        cooldown = {i for i in range(len(active)) if active[i] is None}

    return rows


def max_lane_width(rows: list[GraphRow]) -> int:
    """Mayor ancho simultáneo de lanes en la historia procesada."""
    return max((len(row.lanes) for row in rows), default=0)


__all__ = ["GraphRow", "assign_lanes", "max_lane_width"]
