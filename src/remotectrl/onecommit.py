from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from remotectrl.gitwrap import commit_count_between, head_commit


class CommitContractError(RuntimeError):
    """Raised when `op` did not produce exactly one new commit."""


def run_op(path: Path, op: Callable[[], None]) -> str:
    """Run `op`, verify it produced exactly one new commit on HEAD, return its hash."""
    before = head_commit(path)
    op()
    after = head_commit(path)
    count = commit_count_between(path, before, after)
    if count != 1:
        raise CommitContractError(
            f"expected exactly 1 new commit, op produced {count} (before={before}, after={after})"
        )
    return after
