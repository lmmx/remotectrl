# 2026-09-14: Unit — `gitwrap.ahead_behind`

**Attempting:** `src/remotectrl/gitwrap.py::ahead_behind(path, local_ref, remote_ref)`
**Derived from:** `docs/journal/2026-09-14-gitwrap-first-slice.md` §3 table row: "feeds
`ok()` everywhere" via `rev-list --left-right --count <local>...<remote_ref>`.
**Checkpoint before starting:** `/tmp/remotectrl-checkpoints/20260914T005730-before-ahead-behind`

`git rev-list --left-right --count A...B` prints two tab-separated numbers: commits reachable
from A but not B ("ahead"), then commits reachable from B but not A ("behind"), in that order.
Function returns `(ahead, behind)` as a tuple of ints, parsed directly from that output — no
further interpretation, `ok()` in `policy.py` is what assigns meaning to the numbers.

**Outcome:** done. 4 tests (equal refs, ahead-only, behind-only, diverged) all pass.
Sibling-instance grep: `rev-list`/`left-right`/ahead-behind parsing exists in exactly one
place (`gitwrap.ahead_behind`); no duplicated logic elsewhere.
