"""Sistema de plugins.

Los plugins se registran como entry points del paquete que los provee
en el grupo ``pygit.plugin.api.v1``. Cada entry-point apunta a una
función ``register(api)`` que recibe la API estable y registra sus
extensiones (custom actions, hosting providers, AI backends, themes).

API v1 — versionada para que los plugins puedan declarar la compat
mínima:

```toml
[project.entry-points."pygit.plugin.api.v1"]
my-action = "my_pkg.entry:register"
```

Sandbox razonable: los plugins corren en el mismo proceso pero sus
errores se capturan y loggean, nunca bloquean el arranque.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from collections.abc import Callable


_log = structlog.get_logger()

ENTRY_POINT_GROUP = "pygit.plugin.api.v1"


@dataclass(slots=True)
class CustomAction:
    id: str
    title: str
    category: str
    callback: Callable[[], None]


@dataclass(slots=True)
class PluginAPI:
    """API estable expuesta a los plugins. Cada lista la consume el host."""

    actions: list[CustomAction] = field(default_factory=list)
    hosting_providers: list[type[object]] = field(default_factory=list)
    ai_backends: list[type[object]] = field(default_factory=list)
    themes: list[dict[str, object]] = field(default_factory=list)

    def register_action(self, action: CustomAction) -> None:
        self.actions.append(action)

    def register_hosting_provider(self, provider_cls: type[object]) -> None:
        self.hosting_providers.append(provider_cls)

    def register_ai_backend(self, backend_cls: type[object]) -> None:
        self.ai_backends.append(backend_cls)

    def register_theme(self, theme: dict[str, object]) -> None:
        self.themes.append(theme)


def discover_plugins() -> PluginAPI:
    api = PluginAPI()
    try:
        from importlib.metadata import entry_points
    except ImportError:  # pragma: no cover
        return api
    for ep in entry_points(group=ENTRY_POINT_GROUP):
        try:
            register = ep.load()
            register(api)
            _log.info("plugin loaded", name=ep.name)
        except Exception as exc:
            _log.warning("plugin failed", name=ep.name, error=str(exc))
    return api


__all__ = ["ENTRY_POINT_GROUP", "CustomAction", "PluginAPI", "discover_plugins"]
