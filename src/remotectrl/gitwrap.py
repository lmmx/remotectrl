"""Every git subprocess call in remotectrl lives here."""

from __future__ import annotations

import subprocess
from pathlib import Path

from remotectrl.errors import GitError


def _run(
    path: Path, args: list[str], check: bool = True
) -> subprocess.CompletedProcess[str]:
    cmd = ["git", "-C", str(path), *args]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        raise GitError(f"{' '.join(cmd)}: {result.stderr.strip()}")
    return result


def current_branch(path: Path) -> str:
    """The branch currently checked out. Raises GitError if HEAD is detached."""
    result = _run(path, ["symbolic-ref", "-q", "--short", "HEAD"])
    branch = result.stdout.strip()
    if not branch:
        raise GitError(f"{path}: HEAD is not a branch (detached)")
    return branch


def local_branches(path: Path) -> list[str]:
    """Names of every local branch."""
    result = _run(path, ["for-each-ref", "--format=%(refname:short)", "refs/heads"])
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def head_commit(path: Path) -> str:
    """The commit hash HEAD currently points to."""
    result = _run(path, ["rev-parse", "HEAD"])
    return result.stdout.strip()


def ahead_behind(path: Path, local_ref: str, remote_ref: str) -> tuple[int, int]:
    """(commits in local_ref not in remote_ref, commits in remote_ref not in local_ref)."""
    result = _run(
        path, ["rev-list", "--left-right", "--count", f"{local_ref}...{remote_ref}"]
    )
    ahead_str, behind_str = result.stdout.split()
    return int(ahead_str), int(behind_str)


def fetch_all(path: Path, remote: str) -> None:
    """Fetch every branch from `remote` into this repo's remote-tracking refs."""
    _run(path, ["fetch", remote, "refs/heads/*:refs/remotes/" + remote + "/*"])


def push_branch(path: Path, remote: str, branch: str) -> None:
    """Push HEAD to `branch` on `remote`."""
    _run(path, ["push", remote, f"HEAD:refs/heads/{branch}"])


def remote_names(path: Path) -> list[str]:
    """Names of every remote configured in this repo (`git remote -v` names, deduplicated)."""
    result = _run(path, ["remote"])
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def ref_exists(path: Path, ref: str) -> bool:
    """Whether `ref` resolves to a commit."""
    result = _run(path, ["rev-parse", "--verify", "--quiet", ref], check=False)
    return result.returncode == 0


def commit_count_between(path: Path, before: str, after: str) -> int:
    """Number of commits reachable from `after` but not `before`."""
    result = _run(path, ["rev-list", "--count", f"{before}..{after}"])
    return int(result.stdout.strip())


def commit_count(path: Path, ref: str) -> int:
    """Total number of commits reachable from `ref`."""
    result = _run(path, ["rev-list", "--count", ref])
    return int(result.stdout.strip())
