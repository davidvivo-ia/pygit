"""Contenedor de servicios inyectables.

Construido una sola vez en :mod:`pygit.app.bootstrap`. Las views reciben el
``Services`` para crear sus VMs sin importar directamente la capa de dominio.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pygit.domain.git import GitCli, GitEngine
    from pygit.infra.config import AppConfig
    from pygit.infra.workers import WorkerPool


@dataclass(slots=True, frozen=True)
class Services:
    """Agregado de servicios disponibles para la UI."""

    config: AppConfig
    workers: WorkerPool
    git_engine: GitEngine
    git_cli: GitCli
