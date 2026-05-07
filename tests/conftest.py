"""Configuración global de pytest.

- Fuerza ``QT_QPA_PLATFORM=offscreen`` para que la suite corra en CI Windows
  sin sesión interactiva (también útil en local headless).
- pytest-qt provee la fixture ``qtbot``; aquí no la redefinimos.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
