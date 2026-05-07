"""Parser de ``git --version``."""

from __future__ import annotations

import pytest

from pygit.domain.git.version import MIN_SUPPORTED, GitVersion


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        ("git version 2.45.1\n", GitVersion(2, 45, 1)),
        ("git version 2.45.1.windows.1\n", GitVersion(2, 45, 1)),
        ("git version 2.20.0 (Apple Git-99)", GitVersion(2, 20, 0)),
        ("  git version 2.30.2  ", GitVersion(2, 30, 2)),
    ],
)
def test_parse(output: str, expected: GitVersion) -> None:
    assert GitVersion.parse(output) == expected


def test_parse_rejects_garbage() -> None:
    with pytest.raises(ValueError, match="Cannot parse"):
        GitVersion.parse("no version here")


def test_ordering() -> None:
    assert GitVersion(2, 30, 0) > GitVersion(2, 20, 0)
    assert GitVersion(2, 20, 0) >= MIN_SUPPORTED
    assert GitVersion(2, 19, 9) < MIN_SUPPORTED


def test_str_format() -> None:
    assert str(GitVersion(2, 45, 1)) == "2.45.1"
