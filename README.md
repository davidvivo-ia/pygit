# pygit

Cliente Git de escritorio en Python para Windows. Paridad funcional como objetivo
con SmartGit, GitKraken, SourceTree y SourceGit. Construido sobre PySide6 + libgit2.

> **Estado:** v0.1.0a0 — Fase 0 (andamio). Sin funcionalidad Git todavía.

## Decisiones del producto (v1.0)

| Tema | Decisión |
|---|---|
| Lenguaje | Python 3.11+ |
| GUI | PySide6 (Qt 6.7+, LGPL) |
| Motor Git | pygit2 (libgit2) + git CLI híbrido |
| Plataforma | Windows x64 |
| Empaquetado | PyInstaller `--onedir`, sin instalador. Distribución como ZIP |
| Licencia | MIT |
| Idiomas UI | español (primario) + inglés |
| Telemetría | ninguna |
| AI | opt-in: OpenAI / Anthropic / Ollama local |

Consulta `docs/architecture.md` para arquitectura, threading model y trade-offs.

## Desarrollo

Requisitos: Python 3.11+ y Git 2.20+ instalados en el host.

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -e .[dev]

# Lint, tipos, tests
ruff check .
ruff format --check .
mypy --strict src/pygit
pytest

# Arranque
python -m pygit
```

## Lockfiles

`requirements.in` y `requirements-dev.in` son las fuentes. Compilados con `pip-tools`:

```powershell
pip-compile requirements.in
pip-compile requirements-dev.in
```

## Estructura

```
src/pygit/
  app/          entry point, bootstrap, contenedor de servicios
  ui/           views, viewmodels, widgets, themes, i18n
  domain/       git, diff, hosting, ai, credentials
  infra/        config, logging, fs, net
  resources/    iconos, themes, traducciones
tests/          unitarios + UI con pytest-qt
docs/           arquitectura y decisiones
```

## Licencia

MIT — ver `LICENSE`.
