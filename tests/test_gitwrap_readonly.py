from collections.abc import Callable
from pathlib import Path

import pytest

from remotectrl.errors import GitError
from remotectrl.gitwrap import current_branch, head_commit, local_branches


def test_current_branch(git_repo: Path) -> None:
    assert current_branch(git_repo) == "main"


def test_current_branch_after_checkout(git_repo: Path, git: Callable) -> None:
    git(git_repo, "checkout", "-q", "-b", "other")
    assert current_branch(git_repo) == "other"


def test_current_branch_detached_head_raises(git_repo: Path, git: Callable) -> None:
    sha = head_commit(git_repo)
    git(git_repo, "checkout", "-q", sha)
    with pytest.raises(GitError):
        current_branch(git_repo)


def test_local_branches_single(git_repo: Path) -> None:
    assert local_branches(git_repo) == ["main"]


def test_local_branches_multiple(git_repo: Path, git: Callable) -> None:
    git(git_repo, "branch", "feature-a")
    git(git_repo, "branch", "feature-b")
    assert sorted(local_branches(git_repo)) == ["feature-a", "feature-b", "main"]


def test_head_commit_matches_rev_parse(git_repo: Path, git: Callable) -> None:
    expected = git(git_repo, "rev-parse", "HEAD").stdout.strip()
    assert head_commit(git_repo) == expected


def test_head_commit_changes_after_commit(git_repo: Path, commit: Callable) -> None:
    before = head_commit(git_repo)
    after = commit(git_repo, "more.txt", "more", "second commit")
    assert before != after
    assert head_commit(git_repo) == after
