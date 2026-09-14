from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from remotectrl.config import RemoteType
from remotectrl.errors import GitError
from remotectrl.gitwrap import (
    ahead_behind,
    commit_count,
    current_branch,
    push_branch,
    ref_exists,
)
from remotectrl.markers import PendingPush, clear_marker, write_marker


class PushError(RuntimeError):
    """Raised when a push to one or more configured remotes fails. The local commit is
    left intact. If multiple remotes failed, all are named in the message."""


def run_postflight(path: Path, remotes: dict[str, RemoteType]) -> None:
    """Push the current branch to every non-UNSYNCED remote, in order. Every remote is
    attempted regardless of earlier failures; failures write a pending-push marker each
    and are raised together as a single PushError once all remotes have been tried."""
    branch = current_branch(path)
    failures: list[str] = []

    for remote, remote_type in remotes.items():
        if remote_type == RemoteType.UNSYNCED:
            continue

        try:
            push_branch(path, remote, branch)
        except GitError as exc:
            write_marker(
                path,
                remote,
                PendingPush(
                    branch=branch,
                    commits=_unpushed_count(path, remote, branch),
                    since=datetime.now(UTC).isoformat(),
                    last_attempt_error=str(exc),
                ),
            )
            failures.append(f"{remote}: push failed: {exc}")
            continue

        clear_marker(path, remote)

    if failures:
        raise PushError("; ".join(failures))


def _unpushed_count(path: Path, remote: str, branch: str) -> int:
    remote_ref = f"refs/remotes/{remote}/{branch}"
    if ref_exists(path, remote_ref):
        ahead, _behind = ahead_behind(path, branch, remote_ref)
        return ahead
    return commit_count(path, branch)
