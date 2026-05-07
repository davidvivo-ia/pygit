"""Sequence editor para ``git rebase -i`` invocado por pygit.

Git nos pasa la ruta del fichero ``git-rebase-todo``; nosotros leemos
``PYGIT_REBASE_TODO`` del entorno y lo escribimos sobre ese fichero.
Si la variable no existe, dejamos el fichero como está (modo no
controlado por la app, p. ej. usuario corriendo ``git rebase -i``
manualmente desde la terminal embebida).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 2:
        return 1
    todo_path = Path(sys.argv[1])
    payload = os.environ.get("PYGIT_REBASE_TODO")
    if payload is None:
        return 0
    todo_path.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
