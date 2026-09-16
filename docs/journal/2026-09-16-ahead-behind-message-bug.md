# 2026-09-16: `DivergenceError` silently dropped `ahead` from its own-branch message

**Status:** fixed
**Found by:** the user, running the freshly-integrated `sumac sources` against real data —
accidentally committed while checked out on the wrong writer branch, making it both 1 ahead and
1 behind `umbrel`'s copy of that branch. `sumac sources` (via sumac's `status_text`, which just
formats whatever `DivergenceError` says) reported "1 commit(s) behind" — never mentioning the
local commit that was also sitting there unpushed. Read as "will resolve on its own," when the
real state needed manual resolution (the branch itself was wrong).

## Root cause

`run_preflight`'s own-branch check (`preflight.py`, `check_own_branch` block) computed both
`ahead` and `behind` via `ahead_behind`, but the message on `ok(...)` failing only ever used
`behind`:

```python
ahead, behind = ahead_behind(path, branch, own_remote_ref)
if not ok(ahead, behind, mine=True):
    raise DivergenceError(
        f"{remote}: local branch {branch!r} is {behind} commit(s) behind"
    )
```

`ok(ahead, behind, mine=True)` is `behind == 0` — it correctly triggers on any nonzero `behind`
regardless of `ahead`, but the message never checked whether `ahead` was *also* nonzero. A branch
that's both ahead and behind is a materially different, harder situation than one that's only
behind (the former needs a real merge/rebase decision; the latter can often just be "wait for a
fast-forward" or, per sumac's `remote_sync.fetch_before_read`, resolved automatically on a read).
Folding both into identical wording actively misleads about which case you're in.

## Fix

```python
if not ok(ahead, behind, mine=True):
    if ahead > 0:
        raise DivergenceError(
            f"{remote}: local branch {branch!r} has diverged "
            f"({ahead} ahead, {behind} behind) — cannot resolve automatically"
        )
    raise DivergenceError(
        f"{remote}: local branch {branch!r} is {behind} commit(s) behind"
    )
```

Added `test_mirror_own_branch_ahead_and_behind_reports_both` (`tests/test_preflight.py`) —
commits once on the remote's copy of the branch and once locally after fetching, so both
`ahead` and `behind` are 1, and asserts the message contains `"1 ahead"`, `"1 behind"`, and
`"diverged"`. Confirmed this test fails against the pre-fix code (reproduces exactly the reported
wording) and passes after.

## Sibling-instance check

Grepped every `ahead_behind` call site in this package:

- `preflight.py`'s **other-branches** check (`mine=False`, `ok(...)` is `ahead == 0`): correctly
  reports only `ahead` — `behind` isn't part of that violation (a branch being behind a branch
  this repo doesn't own is the expected steady state), so this isn't the same bug. Left as is.
- `postflight.py`'s `_unpushed_count` discards `behind` on purpose — it's counting local commits
  not yet pushed (`ahead`), not formatting a divergence message. Not the same bug. Left as is.

The sumac-side integration (`sumac/remote_sync.py`) had the identical bug in its own backup-type
own-branch check, independently of this one — fixed there too, same day; see that repo's
`docs/journal/2026-09-16-ahead-behind-divergence-message-bug.md`.
