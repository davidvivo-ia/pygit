"""Tareas AI de alto nivel: commit message, PR description, explicar commit.

Cada función toma un :class:`AiBackend`, prepara un prompt sensato y
filtra secretos antes de enviarlo cuando ``scrub=True`` (default para
backends cloud).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pygit.domain.ai import Message, scrub_secrets

if TYPE_CHECKING:
    from pygit.domain.ai import AiBackend


_SYSTEM_COMMIT = (
    "You are a senior software engineer. Generate a concise Git commit "
    "message following Conventional Commits. Title under 50 characters; "
    "optional body wrapped at 72 characters. Output only the message."
)

_SYSTEM_EXPLAIN = (
    "You are a senior software engineer. Explain what the following diff does, "
    "in plain language, focusing on the why. Be concise."
)

_SYSTEM_PR = (
    "You are a senior software engineer. Draft a Pull Request title and body "
    "for the following diff. Output exactly:\n"
    "TITLE: <one line>\n"
    "BODY:\n<markdown body>"
)


async def generate_commit_message(
    backend: AiBackend, diff: str, *, scrub: bool = True, max_tokens: int = 400
) -> str:
    payload = scrub_secrets(diff) if scrub else diff
    out = await backend.generate(
        [
            Message(role="system", content=_SYSTEM_COMMIT),
            Message(role="user", content=f"Diff:\n```\n{payload}\n```"),
        ],
        max_tokens=max_tokens,
    )
    return out.strip()


async def explain_commit(
    backend: AiBackend, diff: str, *, scrub: bool = True, max_tokens: int = 600
) -> str:
    payload = scrub_secrets(diff) if scrub else diff
    return (
        await backend.generate(
            [
                Message(role="system", content=_SYSTEM_EXPLAIN),
                Message(role="user", content=f"Diff:\n```\n{payload}\n```"),
            ],
            max_tokens=max_tokens,
        )
    ).strip()


async def generate_pr_text(
    backend: AiBackend, diff: str, *, scrub: bool = True, max_tokens: int = 800
) -> tuple[str, str]:
    payload = scrub_secrets(diff) if scrub else diff
    raw = await backend.generate(
        [
            Message(role="system", content=_SYSTEM_PR),
            Message(role="user", content=f"Diff:\n```\n{payload}\n```"),
        ],
        max_tokens=max_tokens,
    )
    title = ""
    body_lines: list[str] = []
    in_body = False
    for line in raw.splitlines():
        if line.startswith("TITLE:") and not title:
            title = line.split(":", 1)[1].strip()
            continue
        if line.startswith("BODY:"):
            in_body = True
            continue
        if in_body:
            body_lines.append(line)
    return title, "\n".join(body_lines).strip()


__all__ = ["explain_commit", "generate_commit_message", "generate_pr_text"]
