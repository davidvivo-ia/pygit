"""Configuración persistente en TOML.

- Path resolución vía :mod:`platformdirs` (Roaming AppData en Windows).
- Lectura tolerante: si no hay fichero, devuelve defaults.
- Lectura segura: parser ``tomllib`` de stdlib (read-only). Para escritura,
  cuando la haya, se usará un writer manual (no inventamos formato propio).
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from platformdirs import user_config_path

if TYPE_CHECKING:
    from pathlib import Path

CONFIG_FILE = "config.toml"
APP_NAME = "pygit"


@dataclass(slots=True, frozen=True)
class UIConfig:
    language: str = "es"
    theme: str = "dark"


@dataclass(slots=True, frozen=True)
class AppConfig:
    ui: UIConfig = field(default_factory=UIConfig)


def config_path() -> Path:
    """Path al config.toml del usuario (no se crea si no existe)."""
    return user_config_path(APP_NAME, appauthor=False, roaming=True) / CONFIG_FILE


def load_config(path: Path | None = None) -> AppConfig:
    """Carga la config. Si no existe el fichero, devuelve defaults."""
    target = path or config_path()
    if not target.exists():
        return AppConfig()
    with target.open("rb") as fh:
        raw: dict[str, Any] = tomllib.load(fh)
    ui_raw: dict[str, Any] = raw.get("ui") or {}
    ui = UIConfig(
        language=str(ui_raw.get("language", "es")),
        theme=str(ui_raw.get("theme", "dark")),
    )
    return AppConfig(ui=ui)


__all__ = ["APP_NAME", "CONFIG_FILE", "AppConfig", "UIConfig", "config_path", "load_config"]
