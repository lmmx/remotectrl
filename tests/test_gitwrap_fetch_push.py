from collections.abc import Callable
from pathlib import Path

from remotectrl.gitwrap import ahead_behind, fetch_all, head_commit, push_branch


def test_fetch_all_populates_tracking_refs(
    git_repo: Path, make_repo: Callable[..., Path], git: Callable, commit: Callable
) -> None:
    remote = make_repo("remote")
    commit(remote, "extra.txt", "extra", "extra commit on remote")
    git(git_repo, "remote", "add", "origin", str(remote))

    fetch_all(git_repo, "origin")

    ahead, behind = ahead_behind(git_repo, "HEAD", "refs/remotes/origin/main")
    assert (ahead, behind) == (0, 1)


def test_fetch_all_fetches_every_branch_not_just_current(
    git_repo: Path, make_repo: Callable[..., Path], git: Callable, commit: Callable
) -> None:
    remote = make_repo("remote")
    git(remote, "branch", "other-branch")
    git(git_repo, "remote", "add", "origin", str(remote))

    fetch_all(git_repo, "origin")

    result = git(git_repo, "for-each-ref", "--format=%(refname)", "refs/remotes/origin")
    refs = result.stdout.split()
    assert "refs/remotes/origin/main" in refs
    assert "refs/remotes/origin/other-branch" in refs


def test_push_branch_creates_remote_branch(
    git_repo: Path, make_repo: Callable[..., Path], git: Callable
) -> None:
    remote = make_repo("remote")
    git(git_repo, "remote", "add", "origin", str(remote))

    push_branch(git_repo, "origin", "mine")

    result = git(remote, "rev-parse", "mine")
    assert result.stdout.strip() == head_commit(git_repo)


def test_push_branch_advances_existing_remote_branch(
    git_repo: Path, make_repo: Callable[..., Path], git: Callable, commit: Callable
) -> None:
    remote = make_repo("remote")
    git(git_repo, "remote", "add", "origin", str(remote))
    push_branch(git_repo, "origin", "mine")
    first = head_commit(git_repo)

    commit(git_repo, "more.txt", "more", "second local commit")
    push_branch(git_repo, "origin", "mine")

    result = git(remote, "rev-parse", "mine")
    assert result.stdout.strip() == head_commit(git_repo)
    assert result.stdout.strip() != first
