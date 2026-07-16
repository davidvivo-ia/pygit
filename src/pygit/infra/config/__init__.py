"""Configuración persistente en TOML.

- Path resolución vía :mod:`platformdirs` (Roaming AppData en Windows).
- Lectura tolerante: si no hay fichero, devuelve defaults.
- Escritura mediante un emisor sencillo (``write_config``) — generamos
  TOML "humano" sin librerías externas para no añadir dependencias.
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
class AiConfigStored:
    enabled: bool = False
    provider: str = "openai"
    model: str = ""


@dataclass(slots=True, frozen=True)
class AppConfig:
    ui: UIConfig = field(default_factory=UIConfig)
    ai: AiConfigStored = field(default_factory=AiConfigStored)


def config_path() -> Path:
    from pathlib import Path as _Path

    return _Path(user_config_path(APP_NAME, appauthor=False, roaming=True)) / CONFIG_FILE


def load_config(path: Path | None = None) -> AppConfig:
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
    ai_raw: dict[str, Any] = raw.get("ai") or {}
    ai = AiConfigStored(
        enabled=bool(ai_raw.get("enabled", False)),
        provider=str(ai_raw.get("provider", "openai")),
        model=str(ai_raw.get("model", "")),
    )
    return AppConfig(ui=ui, ai=ai)


def _quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def write_config(config: AppConfig, path: Path | None = None) -> None:
    target = path or config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# pygit user configuration. Hand-edits are preserved as best-effort:",
        "# unknown keys are ignored on load and rewritten on save only if",
        "# they belong to the schema.",
        "",
        "[ui]",
        f"language = {_quote(config.ui.language)}",
        f"theme = {_quote(config.ui.theme)}",
        "",
        "[ai]",
        f"enabled = {'true' if config.ai.enabled else 'false'}",
        f"provider = {_quote(config.ai.provider)}",
        f"model = {_quote(config.ai.model)}",
        "",
    ]
    target.write_text("\n".join(lines), encoding="utf-8")


__all__ = [
    "APP_NAME",
    "CONFIG_FILE",
    "AiConfigStored",
    "AppConfig",
    "UIConfig",
    "config_path",
    "load_config",
    "write_config",
]
