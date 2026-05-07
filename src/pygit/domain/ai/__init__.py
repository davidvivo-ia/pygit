"""Integración AI conmutable: OpenAI / Anthropic / Ollama.

Diseño:

- :class:`AiBackend` (Protocol): ``generate(messages) -> str``.
- Implementaciones: :class:`OpenAiBackend`, :class:`AnthropicBackend`,
  :class:`OllamaBackend`. Todas hablan REST directo via httpx; sin SDKs
  propietarios.
- :func:`build_backend` lee la configuración (proveedor, modelo, key)
  y devuelve la instancia adecuada.

Privacy first:

- Todo es **opt-in**: si el usuario no configura proveedor, las
  funciones de :mod:`tasks` no se llaman.
- :func:`scrub_secrets` aplica regexes tipo gitleaks sobre el
  payload antes de enviarlo a un proveedor cloud, sustituyéndolos por
  ``[REDACTED]``. Para los backends locales (Ollama) se puede saltar
  con ``skip_scrubbing=True``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

import httpx

# --- Backends ------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class Message:
    role: str  # "system" | "user" | "assistant"
    content: str


class AiBackend(Protocol):
    name: str

    async def generate(self, messages: list[Message], *, max_tokens: int = 800) -> str: ...


class OpenAiBackend:
    name = "openai"

    def __init__(
        self, api_key: str, model: str = "gpt-4o-mini", *, base_url: str | None = None
    ) -> None:
        self._key = api_key
        self._model = model
        self._base = base_url or "https://api.openai.com"

    async def generate(self, messages: list[Message], *, max_tokens: int = 800) -> str:
        payload = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self._base}/v1/chat/completions",
                headers={"Authorization": f"Bearer {self._key}"},
                json=payload,
            )
            resp.raise_for_status()
        data = resp.json()
        return str(data["choices"][0]["message"]["content"])


class AnthropicBackend:
    name = "anthropic"

    def __init__(self, api_key: str, model: str = "claude-3-5-haiku-latest") -> None:
        self._key = api_key
        self._model = model

    async def generate(self, messages: list[Message], *, max_tokens: int = 800) -> str:
        # Anthropic separates system into its own field.
        system = "\n\n".join(m.content for m in messages if m.role == "system")
        chat = [{"role": m.role, "content": m.content} for m in messages if m.role != "system"]
        payload = {
            "model": self._model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": chat,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self._key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
        data = resp.json()
        # Concatenate content blocks.
        return "".join(
            block.get("text", "")
            for block in data.get("content", [])
            if block.get("type") == "text"
        )


class OllamaBackend:
    name = "ollama"

    def __init__(self, model: str = "llama3", base_url: str = "http://localhost:11434") -> None:
        self._model = model
        self._base = base_url

    async def generate(self, messages: list[Message], *, max_tokens: int = 800) -> str:
        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {"num_predict": max_tokens},
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{self._base}/api/chat", json=payload)
            resp.raise_for_status()
        data = resp.json()
        return str(data.get("message", {}).get("content", ""))


# --- Secret scrubbing ----------------------------------------------------------


_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?i)\b(?:api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[A-Za-z0-9/+_\-]{12,}['\"]?"
    ),
    re.compile(r"(?i)AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)ASIA[0-9A-Z]{16}"),
    re.compile(r"(?i)ghp_[A-Za-z0-9]{36}"),
    re.compile(r"(?i)gho_[A-Za-z0-9]{36}"),
    re.compile(r"(?i)github_pat_[A-Za-z0-9_]{82}"),
    re.compile(r"(?i)glpat-[A-Za-z0-9_-]{20}"),
    re.compile(r"(?i)xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"sk-[A-Za-z0-9]{32,}"),
    re.compile(r"(?i)-----BEGIN [A-Z ]+PRIVATE KEY-----[\s\S]+?-----END [A-Z ]+PRIVATE KEY-----"),
)


def scrub_secrets(text: str) -> str:
    out = text
    for pattern in _SECRET_PATTERNS:
        out = pattern.sub("[REDACTED]", out)
    return out


# --- Factory -------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class AiConfig:
    provider: str  # "openai" | "anthropic" | "ollama"
    model: str = ""
    api_key: str = ""
    base_url: str | None = None


def build_backend(config: AiConfig) -> AiBackend:
    if config.provider == "openai":
        return OpenAiBackend(
            api_key=config.api_key,
            model=config.model or "gpt-4o-mini",
            base_url=config.base_url,
        )
    if config.provider == "anthropic":
        return AnthropicBackend(
            api_key=config.api_key, model=config.model or "claude-3-5-haiku-latest"
        )
    if config.provider == "ollama":
        return OllamaBackend(
            model=config.model or "llama3",
            base_url=config.base_url or "http://localhost:11434",
        )
    raise ValueError(f"unknown AI provider {config.provider!r}")


__all__ = [
    "AiBackend",
    "AiConfig",
    "AnthropicBackend",
    "Message",
    "OllamaBackend",
    "OpenAiBackend",
    "build_backend",
    "scrub_secrets",
]
