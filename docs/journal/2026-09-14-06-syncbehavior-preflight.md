# 2026-09-14: Unit — `SyncBehavior` table + preflight

**Attempting:** `src/remotectrl/behavior.py::SyncBehavior`, `BEHAVIOR` table;
`src/remotectrl/preflight.py::run_preflight`
**Derived from:**
- Table: `docs/journal/2026-09-14-gitwrap-first-slice.md` §1 (`SyncBehavior` dataclass and
  `BEHAVIOR: dict[RemoteType, SyncBehavior]` shown verbatim there)
- Preflight orchestration: sumac `docs/journal/2026-09-13-remotectrl-design.md` §5, as
  amended 2026-09-14 (generic fetch, structural other-branches detection, `ok()` predicate)
**Checkpoint before starting:** `/tmp/remotectrl-checkpoints/20260914T010218-before-syncbehavior`

Preflight, per §5:
- `unsynced`: skip entirely (behavior row: `fetch=False, check_own_branch=False,
  check_other_branches=False`).
- Fetch failure (any remote type with `fetch=True`): warn (return, don't raise) — §5's
  "warn and proceed" for transport failure.
- Fetch succeeds, `check_own_branch=True`: `ok(ahead, behind, mine=True)` on current branch
  vs `refs/remotes/<remote>/<current_branch>`. `False` → block (raise, not warn — §5's "real
  divergence" is hard).
- `check_other_branches=True` (mirror only): for every local branch except current with a
  matching `refs/remotes/<remote>/<branch>`, `ok(ahead, behind, mine=False)`. `False` → block.

**Open question surfaced:** what does preflight *return* to signal block vs proceed vs warned?
The design doc describes behavior ("block," "warn and proceed") but not a call-and-return
shape a caller programs against. Choosing an exception-based approach as the conservative
option (loud failure by default is easier to relax than silent failure is to retrofit) —
flagging this now, before writing code, per session rule 1: pointing at §5 justifies *what*
blocks and what warns, but not *how the caller finds out*, which I'm choosing rather than
deriving.

**Second open question surfaced:** §5 doesn't address the first-ever-sync case — a branch
that has never been pushed has no `refs/remotes/<remote>/<branch>` to compare against, and
`ahead_behind` would error on a nonexistent ref rather than produce a meaningful count. Added
`gitwrap.ref_exists` and treating "remote-tracking ref doesn't exist" as "nothing to check,
not a divergence" (skip, don't warn or block) — conservative in the sense that a branch that
has genuinely never synced anywhere can't have "fallen behind" anything yet. Flagging this as
picked, not derived, same as the return-shape question above.

**Outcome:** done, pending review response below. `src/remotectrl/behavior.py`,
`src/remotectrl/preflight.py`, `gitwrap.ref_exists` added. Initial 8 tests passed; found and
removed a self-inflicted no-op branch-rename dance in `test_backup_remote_ahead_blocks` during
my own re-read (not a correctness bug, just confusing test setup that didn't test anything
the simpler version didn't already cover).

**Independent review** (diff-only, no journal/test access) found:

1. **Real deviation, fixed:** `run_preflight` used `"HEAD"` instead of `branch` in the
   own-branch `ahead_behind` call, while the other-branches loop used the actual branch name
   (`other`) — an unexplained asymmetry the reviewer correctly flagged as unspecified.
   Equivalent behavior (HEAD == branch at that point) but inconsistent style. Changed to
   `branch` for consistency; verified no behavior change (42/42 still pass).
2. **Real deviation, deliberately kept, documented here rather than silently accepted:**
   §5's text describes backup fetching only "the current branch (or whatever refs it holds)"
   — narrower than mirror's fully generic fetch. This implementation calls `fetch_all`
   (the fully generic fetch) for *both* `mirror` and `backup`, because `SyncBehavior.fetch`
   is a single boolean in the table (§1's Kolmogorov-minimal design: behavior is data, one
   `fetch: bool` per remote type, not a fetch-scope enum) — introducing a second fetch
   function just for backup's narrower scope would reintroduce the per-type branching the
   table exists to eliminate, for a difference with no observable effect: backup never runs
   `check_other_branches`, so the extra tracking refs `fetch_all` creates for other branches
   are simply unused, never read, never a source of incorrect behavior. §5's "(or whatever
   refs it holds)" parenthetical already signals backup's exact fetch scope isn't
   load-bearing. Kept as-is; flagging this reasoning explicitly rather than treating the
   review's catch as automatically dispositive, since it's not a correctness bug — the
   `SyncBehavior` table's existing design already resolved this tradeoff before this diff
   was written.
3. **Message-content tests added:** neither block-path test previously asserted *which*
   direction ("ahead" vs "behind") the message named — a real gap (the reviewer's point (c),
   an "easy off-by-message-swap bug" with no test catching it). Added `match="behind"` /
   `match="ahead"` to the two existing `pytest.raises` blocks rather than new tests, since
   the scenarios already existed.
4. **Attempted test for "current branch excluded from other-branches loop," reverted:**
   my first attempt conflated the own-branch and other-branches checks (constructing a
   scenario where the *current* branch's remote copy is ahead, expecting no exception) —
   this is wrong: the own-branch check's `mine=True` predicate correctly blocks exactly that
   state, so the test failed for the *right* reason and I was testing an impossible
   invariant. Confirmed by running it (real failure caught, not hypothesized) rather than
   reasoning it away. The coverage the review actually wanted already exists in
   `test_mirror_own_branch_ahead_does_not_block` (current branch ahead of its own remote
   copy does not raise) — the own-branch and other-branches loops are mutually exclusive by
   construction (`if other == branch: continue`), so no state can simultaneously exercise
   both, and no separate test is possible for "excluded from the other-branches loop" beyond
   what the own-branch-ahead test already proves by not raising.
5. **Never-pushed-branch skip and fetch-failure-then-continue** (reviewer's points (a), (b)):
   already covered by `test_first_ever_sync_no_remote_ref_yet_does_not_block` and
   `test_transport_failure_is_a_warning_not_a_raise` respectively — expected gaps in a
   diff-only review with no test-suite visibility.

Final: 42/42 tests pass.
