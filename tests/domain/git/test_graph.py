"""Tests del algoritmo de lanes (``pygit.domain.git.graph``)."""

from __future__ import annotations

from datetime import UTC, datetime

from pygit.domain.git.graph import GraphRow, assign_lanes, max_lane_width
from pygit.domain.git.models import CommitSummary, Signature


def _commit(sha: str, *parents: str, summary: str = "") -> CommitSummary:
    sig = Signature(name="t", email="t@e", when=datetime(2026, 1, 1, tzinfo=UTC))
    return CommitSummary(
        sha=sha,
        short_sha=sha[:7],
        summary=summary or sha,
        message=summary or sha,
        author=sig,
        committer=sig,
        parents=parents,
    )


def test_empty_history() -> None:
    assert assign_lanes([]) == []


def test_linear_history_single_lane() -> None:
    rows = assign_lanes([_commit("c", "b"), _commit("b", "a"), _commit("a")])
    assert [r.lane for r in rows] == [0, 0, 0]
    assert [r.color for r in rows] == [0, 0, 0]
    assert rows[0].incoming == ()
    assert rows[0].outgoing == (0,)
    assert rows[1].incoming == (0,)
    assert rows[1].outgoing == (0,)
    assert rows[2].incoming == (0,)
    assert rows[2].outgoing == ()
    assert rows[2].lanes == (None,)


def test_two_independent_roots_get_distinct_lanes() -> None:
    """Dos roots aislados consecutivos NO deben compartir lane.

    El algoritmo aplica un cooldown de 1 fila a las lanes recién liberadas
    para que la separación entre historias desconectadas sea visible.
    """
    rows = assign_lanes([_commit("a"), _commit("b")])
    assert rows[0].lane == 0
    assert rows[1].lane == 1
    # Colores distintos porque son índices de lane distintos.
    assert rows[0].color != rows[1].color


def test_reuse_lane_after_cooldown_elapses() -> None:
    # DAG:
    #   a  (root, lane 0)
    #   b  (root, lane 1 por cooldown)
    #   c  (parent d, expects d — puede reusar lane 0 porque hace >1 fila
    #       que quedó libre y no se procesó nada en su lane)
    #   d  (root, lane 0 idealmente)
    rows = assign_lanes([_commit("a"), _commit("b"), _commit("c", "d"), _commit("d")])
    assert rows[0].lane == 0
    assert rows[1].lane == 1
    # `c` allocates a new lane because both 0 and 1 are in cooldown.
    # `d` lands on c's lane (via incoming).
    assert rows[2].lane == 2
    assert rows[3].lane == 2


def test_simple_branch_and_merge() -> None:
    # DAG:    M
    #        / \
    #       L   R
    #        \ /
    #         A
    rows = assign_lanes(
        [
            _commit("M", "L", "R"),
            _commit("L", "A"),
            _commit("R", "A"),
            _commit("A"),
        ]
    )

    assert rows[0].lane == 0
    assert rows[0].incoming == ()
    assert set(rows[0].outgoing) == {0, 1}
    assert rows[0].lanes == (0, 1)

    assert rows[1].lane == 0
    assert rows[1].incoming == (0,)
    assert rows[1].outgoing == (0,)
    assert rows[1].lanes == (0, 1)

    # R: lane 1 termina aquí. Su padre A ya vive en lane 0 → outgoing es (0,)
    # y no abrimos una columna nueva.
    assert rows[2].lane == 1
    assert rows[2].incoming == (1,)
    assert rows[2].outgoing == (0,)
    assert rows[2].lanes[1] is None
    assert rows[2].lanes[0] == 0

    # A: sólo una lane lo espera (la 0).
    assert rows[3].lane == 0
    assert rows[3].incoming == (0,)


def test_octopus_merge_three_parents() -> None:
    rows = assign_lanes(
        [
            _commit("M", "P1", "P2", "P3"),
            _commit("P1"),
            _commit("P2"),
            _commit("P3"),
        ]
    )
    assert rows[0].lane == 0
    assert set(rows[0].outgoing) == {0, 1, 2}
    assert rows[0].lanes == (0, 1, 2)

    assert rows[1].lane == 0
    assert rows[2].lane == 1
    assert rows[3].lane == 2


def test_linear_reuse_via_incoming() -> None:
    # Cadena larga sobre lane 0: cada commit reusa lane 0 vía incoming
    # (su sha == active[0]). Esto es el patrón normal en repos reales.
    chain = [_commit(f"c{i:03d}", f"c{i + 1:03d}") for i in range(20)]
    chain.append(_commit("c020"))
    rows = assign_lanes(chain)
    # Todos en lane 0 salvo si hubiera divergencia.
    assert all(r.lane == 0 for r in rows)
    # Y el ancho total es 1.
    assert max_lane_width(rows) == 1


def test_disconnected_heads_do_not_share_lanes() -> None:
    # Tres cadenas cortas totalmente aisladas — cada una debe vivir en su
    # propia columna. Confirma que el cooldown persiste hasta que la lane
    # es reclamada estructuralmente vía incoming.
    rows = assign_lanes(
        [
            _commit("A", "A2"),
            _commit("B", "B2"),
            _commit("C", "C2"),
            _commit("A2"),
            _commit("B2"),
            _commit("C2"),
        ]
    )
    assert rows[0].lane == 0
    assert rows[1].lane == 1
    assert rows[2].lane == 2
    # Cada terminación reusa su propia lane vía incoming (no roots aislados).
    assert rows[3].lane == 0
    assert rows[4].lane == 1
    assert rows[5].lane == 2


def test_max_lane_width_reports_peak() -> None:
    rows = assign_lanes(
        [
            _commit("M", "P1", "P2", "P3"),
            _commit("P1"),
            _commit("P2"),
            _commit("P3"),
        ]
    )
    assert max_lane_width(rows) == 3


def test_assignment_is_deterministic() -> None:
    sequence = [
        _commit("M", "L", "R"),
        _commit("L", "A"),
        _commit("R", "A"),
        _commit("A"),
    ]
    assert assign_lanes(sequence) == assign_lanes(sequence)


def test_graph_row_is_frozen() -> None:
    rows = assign_lanes([_commit("a")])
    row = rows[0]
    assert isinstance(row, GraphRow)
    try:
        row.lane = 99  # type: ignore[misc]
    except (AttributeError, TypeError):
        pass
    else:  # pragma: no cover
        raise AssertionError("expected frozen dataclass to forbid assignment")


def test_perf_smoke_one_thousand_linear_commits() -> None:
    # Smoke perf: 1k commits lineales deben procesarse sin demora apreciable.
    chain = [_commit(f"c{i:04d}", f"c{i + 1:04d}") for i in range(999)]
    chain.append(_commit("c0999"))
    rows = assign_lanes(chain)
    assert len(rows) == 1000
    assert all(r.lane == 0 for r in rows)
    assert max_lane_width(rows) == 1
