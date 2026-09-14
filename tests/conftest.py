"""Fixtures for building throwaway git repos in tmp dirs."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

_GPG_OFF = ["-c", "commit.gpgsign=false"]


def _git(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(path), *args], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    return result


def init_repo(path: Path, *, branch: str = "main") -> None:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q", "-b", branch)
    _git(path, "config", "user.email", "test@example.invalid")
    _git(path, "config", "user.name", "Test")
    # Real remotes (a bare repo on a git server) never refuse a push to their
    # checked-out branch, because they have no checked-out branch. These fixtures use
    # non-bare repos (so branch/checkout manipulation in tests is simple), so this
    # setting reproduces bare-remote push behavior instead of git's non-bare-specific
    # "refusing to update checked out branch" rejection, which is a fixture-realism
    # concern, not something remotectrl's push behavior needs to handle.
    _git(path, "config", "receive.denyCurrentBranch", "updateInstead")


def commit_file(path: Path, name: str, content: str, message: str) -> str:
    (path / name).write_text(content)
    _git(path, "add", name)
    _git(path, *_GPG_OFF, "commit", "-q", "-m", message)
    return _git(path, "rev-parse", "HEAD").stdout.strip()


@pytest.fixture
def git(tmp_path: Path) -> Callable[..., subprocess.CompletedProcess[str]]:
    return _git


@pytest.fixture
def commit(tmp_path: Path) -> Callable[[Path, str, str, str], str]:
    return commit_file


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    init_repo(repo)
    commit_file(repo, "seed.txt", "seed", "initial commit")
    return repo


@pytest.fixture
def make_repo(tmp_path: Path, git_repo: Path) -> Callable[[str], Path]:
    """Factory for additional repos that share `git_repo`'s history (e.g. a "remote"),
    named to avoid collisions.

    Cloned from `git_repo` rather than given an independently-created seed commit: two
    repos each running `git init` and committing identical *content* do NOT produce the
    same commit — commit hashes include the author/committer timestamp, so two "seed"
    commits only collide if both land in the same wall-clock second, and diverge into
    two unrelated root commits the instant a test straddles a second boundary. A real
    remote and its clone always share a genuine common ancestor; cloning here reproduces
    that instead of relying on timing-dependent hash coincidence.
    """

    def _make(name: str, *, branch: str = "main") -> Path:
        repo = tmp_path / name
        _git(tmp_path, "clone", "-q", "-b", branch, str(git_repo), str(repo))
        _git(repo, "config", "user.email", "test@example.invalid")
        _git(repo, "config", "user.name", "Test")
        _git(repo, "config", "receive.denyCurrentBranch", "updateInstead")
        _git(repo, "remote", "remove", "origin")
        return repo

    return _make
