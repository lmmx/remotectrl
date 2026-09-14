from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from remotectrl.config import resolve
from remotectrl.onecommit import run_op
from remotectrl.postflight import run_postflight
from remotectrl.preflight import run_preflight


def run(repo_path: Path, op: Callable[[], None]) -> str:
    """Preflight every configured remote, run `op` under the one-commit contract, then
    push to every configured remote. Returns the new commit hash."""
    remotes = resolve(repo_path)
    run_preflight(repo_path, remotes)
    commit = run_op(repo_path, op)
    run_postflight(repo_path, remotes)
    return commit
