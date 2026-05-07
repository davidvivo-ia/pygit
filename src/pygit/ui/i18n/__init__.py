"""Internacionalización con ``gettext``.

Las cadenas se marcan en código vía ``_()`` (importado como ``gettext`` para
no chocar con el guion bajo de variables sin uso). Las traducciones viven en
``pygit/resources/translations/<lang>/LC_MESSAGES/pygit.po``.

Estrategia de compilación:

- En desarrollo / runtime, si no existe el ``.mo`` correspondiente al ``.po``,
  se compila al vuelo con :func:`babel.messages.mofile.write_mo`. Esto evita
  un paso de build separado y mantiene reproducibilidad sin depender de
  ``msgfmt`` externo.
- Los ``.mo`` se ignoran en git (ver ``.gitignore``); las fuentes ``.po`` son
  la verdad.
"""

from __future__ import annotations

import gettext as _gettext
from importlib import resources
from pathlib import Path

from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po

DOMAIN = "pygit"
SUPPORTED: tuple[str, ...] = ("es", "en")
DEFAULT_LANGUAGE = "es"


class _State:
    translation: _gettext.NullTranslations = _gettext.NullTranslations()


def _translations_root() -> Path:
    pkg = resources.files("pygit.resources.translations")
    return Path(str(pkg))


def _ensure_mo(language: str, root: Path) -> Path | None:
    locale_dir = root / language / "LC_MESSAGES"
    po_file = locale_dir / f"{DOMAIN}.po"
    mo_file = locale_dir / f"{DOMAIN}.mo"
    if not po_file.exists():
        return None
    if mo_file.exists() and mo_file.stat().st_mtime >= po_file.stat().st_mtime:
        return mo_file
    with po_file.open("rb") as fh:
        catalog = read_po(fh, locale=language, domain=DOMAIN)
    locale_dir.mkdir(parents=True, exist_ok=True)
    with mo_file.open("wb") as fh:
        write_mo(fh, catalog)
    return mo_file


def install_translations(language: str = DEFAULT_LANGUAGE) -> None:
    """Selecciona idioma activo y precompila los ``.mo`` necesarios."""
    root = _translations_root()
    primary = language if language in SUPPORTED else DEFAULT_LANGUAGE
    for lang in SUPPORTED:
        _ensure_mo(lang, root)
    _State.translation = _gettext.translation(
        DOMAIN,
        localedir=str(root),
        languages=[primary],
        fallback=True,
    )


def gettext(message: str) -> str:
    """Traduce ``message`` al idioma activo. Alias canónico de ``_()``."""
    return _State.translation.gettext(message)


__all__ = ["DEFAULT_LANGUAGE", "DOMAIN", "SUPPORTED", "gettext", "install_translations"]
