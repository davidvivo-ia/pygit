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


def test_two_independent_roots_share_lane() -> None:
    """Dos roots aislados consecutivos reutilizan la primera lane.

    Comportamiento aceptado para Phase 1.2: el algoritmo no penaliza la
    reutilización inmediata. Mejora futura (separación visual de
    historias desconectadas) pendiente como pulido.
    """
    rows = assign_lanes([_commit("a"), _commit("b")])
    assert rows[0].lane == 0
    assert rows[1].lane == 0
    assert rows[0].color == rows[1].color


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


def test_lane_reuse_after_parallel_branches_end() -> None:
    # Dos ramas paralelas que terminan, luego un nuevo root aislado.
    # DAG:  X       Y
    #       |       |
    #       X1     Y1
    #
    #       Z (root aislado, posterior en walker order)
    rows = assign_lanes(
        [
            _commit("X", "X1"),
            _commit("Y", "Y1"),
            _commit("X1"),
            _commit("Y1"),
            _commit("Z"),
        ]
    )
    assert rows[0].lane == 0
    assert rows[1].lane == 1
    assert rows[2].lane == 0
    assert rows[3].lane == 1
    # Z reusa la primera lane libre (la 0).
    assert rows[4].lane == 0
    # El color de la lane 0 se mantiene tras la reutilización.
    assert rows[4].color == rows[0].color


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
