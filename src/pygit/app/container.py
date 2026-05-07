"""Contenedor de servicios inyectables.

En Fase 0 sólo expone la configuración. En fases siguientes se inyectarán
``GitEngine``, ``HostingService``, ``AIService``, ``CredentialService``, etc.
La intención es mantener un contenedor minimalista (sin frameworks) que se
construye una sola vez en :mod:`pygit.app.bootstrap` y se pasa a las views.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pygit.infra.config import AppConfig


@dataclass(slots=True, frozen=True)
class Services:
    """Agregado de servicios disponibles para la UI."""

    config: AppConfig
