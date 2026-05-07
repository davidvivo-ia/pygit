"""Carga de themes JSON estilo SourceGit.

Esquema mínimo:

```json
{
  "name": "midnight",
  "kind": "dark",
  "qss": ":root { ... }",
  "graph_palette": ["#89b4fa", "#a6e3a1", ...]
}
```

- ``qss`` se aplica con ``QApplication.setStyleSheet``.
- ``graph_palette`` (8 colores) se inyecta en el delegate del grafo.
- ``kind`` es informativo (``light`` / ``dark`` / ``high-contrast``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from pathlib import Path

_log = structlog.get_logger()


@dataclass(slots=True, frozen=True)
class Theme:
    name: str
    kind: str = "dark"
    qss: str = ""
    graph_palette: tuple[str, ...] = field(default_factory=tuple)


def load_theme(path: Path) -> Theme:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return Theme(
        name=str(raw.get("name") or path.stem),
        kind=str(raw.get("kind") or "dark"),
        qss=str(raw.get("qss") or ""),
        graph_palette=tuple(str(c) for c in raw.get("graph_palette") or ()),
    )


def discover_themes(directories: list[Path]) -> list[Theme]:
    out: list[Theme] = []
    for directory in directories:
        if not directory.exists():
            continue
        for entry in sorted(directory.glob("*.json")):
            try:
                out.append(load_theme(entry))
            except Exception as exc:
                _log.warning("theme load failed", path=str(entry), error=str(exc))
    return out


__all__ = ["Theme", "discover_themes", "load_theme"]
