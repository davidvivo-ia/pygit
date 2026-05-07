"""Gestión de credenciales (HTTPS tokens y claves SSH).

Tres backends:

- ``KeyringStore``: tokens HTTPS por host, almacenados en el llavero del
  SO (Windows Credential Manager en Windows). Wrapper sobre :mod:`keyring`.
- ``SshKeyStore``: localiza claves SSH en ``~/.ssh`` (id_ed25519, id_rsa)
  y produce credenciales :class:`pygit2.Keypair`.
- ``CompositeResolver``: combina ambos eligiendo según la URL.

Diseño:

- ``CredentialResolver.resolve(url, username_from_url)`` devuelve la
  credencial pygit2 apropiada para el flujo libgit2; ``None`` si no hay.
- En la VM se construye el resolver en :func:`build_default_resolver` y
  se inyecta a :func:`pygit.domain.git.remote.fetch/push/clone`.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pygit2

if TYPE_CHECKING:
    from collections.abc import Iterable


KEYRING_SERVICE = "pygit-https"


def _host_from_url(url: str) -> str | None:
    match = re.match(r"^[a-zA-Z]+://(?:[^@/]+@)?([^/:]+)", url)
    return match.group(1).lower() if match else None


# --- HTTPS tokens --------------------------------------------------------------


class KeyringStore:
    """Tokens HTTPS persistidos via :mod:`keyring`.

    La clave es ``host``, el secret es ``"<username>:<token>"`` (separados
    por ``:`` para que ambos vivan en una sola entrada por host).
    """

    def __init__(self, service: str = KEYRING_SERVICE) -> None:
        self._service = service

    def store(self, host: str, username: str, token: str) -> None:
        import keyring

        keyring.set_password(self._service, host.lower(), f"{username}:{token}")

    def lookup(self, host: str) -> tuple[str, str] | None:
        import keyring

        raw = keyring.get_password(self._service, host.lower())
        if not raw or ":" not in raw:
            return None
        username, _, token = raw.partition(":")
        return username, token

    def remove(self, host: str) -> None:
        import keyring

        keyring.delete_password(self._service, host.lower())


# --- SSH keys ------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class SshKey:
    name: str
    private_key: Path
    public_key: Path
    has_passphrase: bool


class SshKeyStore:
    DEFAULT_KEYS = ("id_ed25519", "id_rsa", "id_ecdsa", "id_dsa")

    def __init__(self, ssh_dir: Path | None = None) -> None:
        self._ssh_dir = ssh_dir or Path.home() / ".ssh"

    def list_keys(self) -> list[SshKey]:
        out: list[SshKey] = []
        if not self._ssh_dir.exists():
            return out
        for name in self.DEFAULT_KEYS:
            priv = self._ssh_dir / name
            pub = self._ssh_dir / f"{name}.pub"
            if priv.exists() and pub.exists():
                out.append(
                    SshKey(
                        name=name,
                        private_key=priv,
                        public_key=pub,
                        has_passphrase=self._is_encrypted(priv),
                    )
                )
        return out

    @staticmethod
    def _is_encrypted(priv: Path) -> bool:
        try:
            head = priv.read_text(encoding="utf-8", errors="ignore")[:512]
        except OSError:
            return False
        return "ENCRYPTED" in head or "Proc-Type: 4,ENCRYPTED" in head

    def first_key(self) -> SshKey | None:
        keys = self.list_keys()
        return keys[0] if keys else None


# --- Resolver ------------------------------------------------------------------


class CompositeResolver:
    def __init__(
        self,
        keyring_store: KeyringStore | None = None,
        ssh_store: SshKeyStore | None = None,
    ) -> None:
        self._keyring = keyring_store or KeyringStore()
        self._ssh = ssh_store or SshKeyStore()

    def resolve(self, url: str, username_from_url: str | None) -> pygit2.Credential | None:
        if url.startswith("http://") or url.startswith("https://"):
            host = _host_from_url(url)
            if host is None:
                return None
            cred = self._keyring.lookup(host)
            if cred is None:
                return None
            username, token = cred
            return pygit2.UserPass(username, token)
        # SSH path: ``git@host:user/repo`` or ``ssh://...``
        username = username_from_url or "git"
        key = self._ssh.first_key()
        if key is None:
            return None
        return pygit2.Keypair(
            username,
            str(key.public_key),
            str(key.private_key),
            os.environ.get("PYGIT_SSH_PASSPHRASE", ""),
        )


def build_default_resolver() -> CompositeResolver:
    return CompositeResolver()


def discover_hosts(remote_urls: Iterable[str]) -> set[str]:
    """Extrae los hosts de una lista de URLs (para mostrar en UI)."""
    out: set[str] = set()
    for url in remote_urls:
        host = _host_from_url(url)
        if host:
            out.add(host)
    return out


__all__ = [
    "KEYRING_SERVICE",
    "CompositeResolver",
    "KeyringStore",
    "SshKey",
    "SshKeyStore",
    "build_default_resolver",
    "discover_hosts",
]
