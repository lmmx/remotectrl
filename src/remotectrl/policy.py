from __future__ import annotations


def ok(ahead: int, behind: int, mine: bool) -> bool:
    """Whether a branch's ahead/behind state against a remote is acceptable.

    `mine=True`: acceptable as long as `behind == 0` (any `ahead` is fine).
    `mine=False`: acceptable as long as `ahead == 0` (any `behind` is fine).
    """
    return behind == 0 if mine else ahead == 0
