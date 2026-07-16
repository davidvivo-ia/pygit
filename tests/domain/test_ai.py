"""Tests del módulo AI: scrub_secrets + factory."""

from __future__ import annotations

import pytest

from pygit.domain.ai import (
    AiConfig,
    AnthropicBackend,
    OllamaBackend,
    OpenAiBackend,
    build_backend,
    scrub_secrets,
)


class TestScrubSecrets:
    def test_leaves_normal_code_untouched(self) -> None:
        code = "def foo(x):\n    return x + 1"
        assert scrub_secrets(code) == code

    def test_redacts_ghp_token(self) -> None:
        text = "token: ghp_" + "a" * 36
        assert "[REDACTED]" in scrub_secrets(text)
        assert "ghp_" not in scrub_secrets(text)

    def test_redacts_github_pat(self) -> None:
        text = "GITHUB_PAT=github_pat_" + "x" * 82
        assert "[REDACTED]" in scrub_secrets(text)

    def test_redacts_openai_key(self) -> None:
        text = "OPENAI_API_KEY = 'sk-" + "y" * 40 + "'"
        assert "[REDACTED]" in scrub_secrets(text)

    def test_redacts_aws_akia(self) -> None:
        text = "AWS_KEY=AKIAIOSFODNN7EXAMPLE"
        assert "[REDACTED]" in scrub_secrets(text)

    def test_redacts_slack_token(self) -> None:
        text = "slack: xoxb-1234567890-abcdefgh"
        assert "[REDACTED]" in scrub_secrets(text)

    def test_redacts_private_key_pem(self) -> None:
        text = (
            "-----BEGIN RSA PRIVATE KEY-----\n"
            "MIIEowIBAAKCAQEA0Z9\n...\n"
            "-----END RSA PRIVATE KEY-----"
        )
        assert "MIIEow" not in scrub_secrets(text)
        assert "[REDACTED]" in scrub_secrets(text)

    def test_redacts_generic_secret_assignment(self) -> None:
        text = 'password = "SuperSecret123456"'
        assert "SuperSecret123456" not in scrub_secrets(text)


class TestBuildBackend:
    def test_openai(self) -> None:
        b = build_backend(AiConfig(provider="openai", model="gpt-4o", api_key="k"))
        assert isinstance(b, OpenAiBackend)
        assert b.name == "openai"

    def test_anthropic(self) -> None:
        b = build_backend(AiConfig(provider="anthropic", api_key="k"))
        assert isinstance(b, AnthropicBackend)

    def test_ollama_default_model(self) -> None:
        b = build_backend(AiConfig(provider="ollama"))
        assert isinstance(b, OllamaBackend)

    def test_unknown_provider_raises(self) -> None:
        with pytest.raises(ValueError, match="unknown AI provider"):
            build_backend(AiConfig(provider="claude-3"))
