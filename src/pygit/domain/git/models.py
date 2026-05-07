"""Modelos de dominio inmutables para la capa Git.

Todos son ``frozen=True``, ``slots=True``: barato instanciar masivamente
(50k commits) y seguros para pasar entre hilos.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

SHORT_SHA_LEN = 7


@dataclass(slots=True, frozen=True)
class Signature:
    """Author/committer."""

    name: str
    email: str
    when: datetime


@dataclass(slots=True, frozen=True)
class CommitSummary:
    """Datos suficientes para mostrar un commit en una fila del log."""

    sha: str
    short_sha: str
    summary: str
    message: str
    author: Signature
    committer: Signature
    parents: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class BranchRef:
    name: str
    full_name: str
    target_sha: str
    is_remote: bool
    upstream: str | None = None


@dataclass(slots=True, frozen=True)
class TagRef:
    name: str
    full_name: str
    target_sha: str
    is_annotated: bool
    message: str | None = None


@dataclass(slots=True, frozen=True)
class RemoteRef:
    name: str
    fetch_url: str
    push_url: str | None = None


@dataclass(slots=True, frozen=True)
class HeadInfo:
    is_detached: bool
    is_unborn: bool
    branch_name: str | None
    target_sha: str


__all__ = [
    "SHORT_SHA_LEN",
    "BranchRef",
    "CommitSummary",
    "HeadInfo",
    "RemoteRef",
    "Signature",
    "TagRef",
]
