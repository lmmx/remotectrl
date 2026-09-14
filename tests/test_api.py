from collections.abc import Callable
from pathlib import Path

import pytest

import remotectrl
from remotectrl.gitwrap import head_commit
from remotectrl.postflight import PushError
from remotectrl.preflight import DivergenceError


def test_run_pushes_after_op_with_single_remote_default_mirror(
    git_repo: Path, make_repo: Callable[..., Path], git: Callable, commit: Callable
) -> None:
    remote = make_repo("remote")
    git(git_repo, "remote", "add", "origin", str(remote))

    new_commit = remotectrl.run(
        git_repo, lambda: commit(git_repo, "a.txt", "a", "the op's commit")
    )

    assert new_commit == head_commit(git_repo)
    assert git(remote, "rev-parse", "main").stdout.strip() == new_commit


def test_run_blocks_before_op_runs_when_preflight_finds_divergence(
    git_repo: Path, make_repo: Callable[..., Path], git: Callable, commit: Callable
) -> None:
    remote = make_repo("remote")
    commit(remote, "extra.txt", "extra", "something else pushed to origin/main")
    git(git_repo, "remote", "add", "origin", str(remote))

    before = head_commit(git_repo)
    called = []
    with pytest.raises(DivergenceError):
        remotectrl.run(git_repo, lambda: called.append(1))

    # op must never have run — preflight blocks before it
    assert called == []
    assert head_commit(git_repo) == before


def test_run_raises_pusherror_on_push_failure_but_keeps_the_commit(
    git_repo: Path, git: Callable, commit: Callable
) -> None:
    git(git_repo, "remote", "add", "origin", "/nonexistent/does-not-exist")
    before = head_commit(git_repo)

    with pytest.raises(PushError):
        remotectrl.run(
            git_repo, lambda: commit(git_repo, "a.txt", "a", "the op's commit")
        )

    assert head_commit(git_repo) != before  # commit not rolled back
