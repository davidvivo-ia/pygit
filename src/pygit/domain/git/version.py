"""Detección y comparación de versiones del binario ``git``.

Útil para hacer guards en runtime: features como
``--force-with-lease=ref:expect`` (2.30+), ``rebase --update-refs`` (2.38+)
o sparse-checkout v2 sólo se exponen en la UI si el binario instalado las
soporta. La versión mínima soportada por pygit es 2.20.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")


@dataclass(slots=True, frozen=True, order=True)
class GitVersion:
    """Versión semántica simplificada (major.minor.patch)."""

    major: int
    minor: int
    patch: int

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    @classmethod
    def parse(cls, output: str) -> GitVersion:
        """Extrae la versión de la salida de ``git --version``.

        Acepta variantes como:

        - ``"git version 2.45.1"``
        - ``"git version 2.45.1.windows.1"``
        - ``"git version 2.20.0 (Apple Git-...)"``
        """
        match = _VERSION_RE.search(output)
        if match is None:
            raise ValueError(f"Cannot parse git version from: {output!r}")
        return cls(int(match[1]), int(match[2]), int(match[3]))


MIN_SUPPORTED = GitVersion(2, 20, 0)


__all__ = ["MIN_SUPPORTED", "GitVersion"]
