from __future__ import annotations

from dataclasses import dataclass

from remotectrl.config import RemoteType


@dataclass(frozen=True)
class SyncBehavior:
    fetch: bool
    check_own_branch: bool
    check_other_branches: bool


BEHAVIOR: dict[RemoteType, SyncBehavior] = {
    RemoteType.UNSYNCED: SyncBehavior(
        fetch=False, check_own_branch=False, check_other_branches=False
    ),
    RemoteType.BACKUP: SyncBehavior(
        fetch=True, check_own_branch=True, check_other_branches=False
    ),
    RemoteType.MIRROR: SyncBehavior(
        fetch=True, check_own_branch=True, check_other_branches=True
    ),
}
