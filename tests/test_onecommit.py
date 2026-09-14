from collections.abc import Callable
from pathlib import Path

import pytest

from remotectrl.gitwrap import head_commit
from remotectrl.onecommit import CommitContractError, run_op


def test_exactly_one_commit_succeeds(git_repo: Path, commit: Callable) -> None:
    result = run_op(git_repo, lambda: commit(git_repo, "a.txt", "a", "one commit"))
    assert result == head_commit(git_repo)


def test_zero_commits_raises(git_repo: Path) -> None:
    with pytest.raises(CommitContractError, match="0"):
        run_op(git_repo, lambda: None)


def test_two_commits_raises(git_repo: Path, commit: Callable) -> None:
    def op() -> None:
        commit(git_repo, "a.txt", "a", "first")
        commit(git_repo, "b.txt", "b", "second")

    with pytest.raises(CommitContractError, match="2"):
        run_op(git_repo, op)


def test_failed_contract_does_not_roll_back_commits(
    git_repo: Path, commit: Callable
) -> None:
    # design doc §6/§7: the local commit is never rolled back even when something after
    # it fails — verify the two commits from the failing op are still present afterward.
    before = head_commit(git_repo)

    def op() -> None:
        commit(git_repo, "a.txt", "a", "first")
        commit(git_repo, "b.txt", "b", "second")

    with pytest.raises(CommitContractError):
        run_op(git_repo, op)

    assert head_commit(git_repo) != before


def test_non_linear_history_is_not_specially_detected(
    git_repo: Path, git: Callable, commit: Callable
) -> None:
    # Known, accepted limitation (design doc §6: "no stronger check... the snapshot/diff
    # is sufficient"): run_op only counts commits in the before..after range, so an op
    # that rewrites history (here, amending HEAD instead of adding on top of it) is not
    # distinguished from a normal single new commit even though `before` is not an
    # ancestor of `after`. This test documents that behavior, it isn't asserting it's
    # correct — just that it's not silently different from what the design doc describes.
    def op() -> None:
        (git_repo / "amended.txt").write_text("amended")
        git(git_repo, "add", "amended.txt")
        git(
            git_repo,
            "-c",
            "commit.gpgsign=false",
            "commit",
            "--amend",
            "-q",
            "-m",
            "amended commit",
        )

    result = run_op(git_repo, op)
    assert result == head_commit(git_repo)
