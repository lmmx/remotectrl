from collections.abc import Callable
from pathlib import Path

from remotectrl.gitwrap import ahead_behind


def test_equal_refs_zero_zero(git_repo: Path) -> None:
    assert ahead_behind(git_repo, "HEAD", "HEAD") == (0, 0)


def test_local_ahead(git_repo: Path, git: Callable, commit: Callable) -> None:
    git(git_repo, "branch", "base")
    commit(git_repo, "a.txt", "a", "commit a")
    commit(git_repo, "b.txt", "b", "commit b")
    assert ahead_behind(git_repo, "HEAD", "base") == (2, 0)


def test_local_behind(git_repo: Path, git: Callable, commit: Callable) -> None:
    git(git_repo, "branch", "ahead-branch")
    git(git_repo, "checkout", "-q", "ahead-branch")
    commit(git_repo, "a.txt", "a", "commit a")
    git(git_repo, "checkout", "-q", "main")
    assert ahead_behind(git_repo, "HEAD", "ahead-branch") == (0, 1)


def test_diverged(git_repo: Path, git: Callable, commit: Callable) -> None:
    git(git_repo, "branch", "other")
    commit(git_repo, "on-main.txt", "m", "main-only commit")
    git(git_repo, "checkout", "-q", "other")
    commit(git_repo, "on-other.txt", "o", "other-only commit")
    git(git_repo, "checkout", "-q", "main")
    assert ahead_behind(git_repo, "HEAD", "other") == (1, 1)
