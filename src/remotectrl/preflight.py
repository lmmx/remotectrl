from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from remotectrl.behavior import BEHAVIOR
from remotectrl.config import RemoteType
from remotectrl.errors import GitError
from remotectrl.gitwrap import (
    ahead_behind,
    current_branch,
    fetch_all,
    local_branches,
    ref_exists,
)
from remotectrl.markers import read_marker
from remotectrl.policy import ok


class DivergenceError(RuntimeError):
    """Raised when preflight finds a real ahead/behind divergence that must block the op."""


@dataclass(frozen=True)
class PreflightWarning:
    remote: str
    message: str


def run_preflight(path: Path, remotes: dict[str, RemoteType]) -> list[PreflightWarning]:
    """Fetch and check every configured remote. Returns transport-failure warnings.
    Raises DivergenceError on a real divergence."""
    warnings: list[PreflightWarning] = []
    branch = current_branch(path)

    for remote, remote_type in remotes.items():
        pending = read_marker(path, remote)
        if pending is not None:
            warnings.append(
                PreflightWarning(
                    remote,
                    f"{pending.commits} commit(s) still unpushed since {pending.since} "
                    f"(last attempt: {pending.last_attempt_error})",
                )
            )

        behavior = BEHAVIOR[remote_type]
        if not behavior.fetch:
            continue

        try:
            fetch_all(path, remote)
        except GitError as exc:
            warnings.append(PreflightWarning(remote, str(exc)))
            continue

        if behavior.check_own_branch:
            own_remote_ref = f"refs/remotes/{remote}/{branch}"
            if ref_exists(path, own_remote_ref):
                ahead, behind = ahead_behind(path, branch, own_remote_ref)
                if not ok(ahead, behind, mine=True):
                    raise DivergenceError(
                        f"{remote}: local branch {branch!r} is {behind} commit(s) behind"
                    )

        if behavior.check_other_branches:
            for other in local_branches(path):
                if other == branch:
                    continue
                other_remote_ref = f"refs/remotes/{remote}/{other}"
                if not ref_exists(path, other_remote_ref):
                    continue
                ahead, behind = ahead_behind(path, other, other_remote_ref)
                if not ok(ahead, behind, mine=False):
                    raise DivergenceError(
                        f"{remote}: local branch {other!r} is {ahead} commit(s) "
                        "ahead of a branch it doesn't own"
                    )

    return warnings
