"""Permite ejecutar la app con ``python -m pygit``."""

from __future__ import annotations

from pygit.app.main import main

if __name__ == "__main__":
    raise SystemExit(main())
