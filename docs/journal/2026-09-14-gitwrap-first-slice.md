# 2026-09-14: The One-Predicate Kernel and First Implementation Slice

**Status:** scoped, no code written
**Depends on:** sumac `docs/journal/2026-09-13-remotectrl-design.md` §2, §4, §5 (§5 amended
2026-09-14 alongside this entry — see below)

---

## 1. The kernel

Design doc §2 states the whole point of this package in one sentence: "This single rule
produces both remote types' behavior as special cases — no separate rules needed." Everything
`remotectrl` checks reduces to one pure predicate:

```python
def ok(ahead: int, behind: int, mine: bool) -> bool:
    return behind == 0 if mine else ahead == 0
```

- Mirror's own-branch check (§5): `ok(ahead, behind, mine=True)`.
- Mirror's other-branches check (§5): `ok(ahead, behind, mine=False)`.
- Backup's remote-ahead check (§3): `ok(ahead, behind, mine=True)` — **the identical call**
  mirror makes for its own branch, not a separate rule. Backup never evaluates `mine=False` on
  anything, because it never fetches or reasons about any branch but its own.

`RemoteType` (`unsynced` / `mirror` / `backup`) does not branch behavior with `if`/`elif`
anywhere in the implementation. It selects a row in a static table; the table's fields are the
only place remote-type-specific behavior exists:

```python
@dataclass(frozen=True)
class SyncBehavior:
    fetch: bool
    check_own_branch: bool       # run ok(..., mine=True) on the current branch
    check_other_branches: bool   # run ok(..., mine=False) on every other local branch

BEHAVIOR: dict[RemoteType, SyncBehavior] = {
    RemoteType.UNSYNCED: SyncBehavior(fetch=False, check_own_branch=False, check_other_branches=False),
    RemoteType.BACKUP:   SyncBehavior(fetch=True,  check_own_branch=True,  check_other_branches=False),
    RemoteType.MIRROR:   SyncBehavior(fetch=True,  check_own_branch=True,  check_other_branches=True),
}
```

Per-call, config resolution (`.rc/remotes.toml` name → `RemoteType`, including the
2026-09-13 resolved rule that a name absent from local `git remote -v` resolves to
`unsynced`) is necessarily dynamic — it has to be re-read every call, on whatever branch and
clone is current. What's static is everything downstream of that lookup: `RemoteType →
SyncBehavior` never changes, so behavior is a table lookup, not scattered conditionals.
Config resolution feeding a static behavior table is the intended shape, not "static table
*or* per-call resolution" as a fork — they're different layers.

## 2. Amendment this scoping forced: no branch-naming convention anywhere

Deriving `check_other_branches`'s *mechanism* (not just its boolean) surfaced that the design
doc's §5 and §7, as originally written, both baked sumac's `writer/<id>` naming into a package
§4 explicitly declares naming-agnostic ("`remotectrl` has no concept of 'user' — only 'the
branch currently checked out'"). Fixed at the design-doc level first (sumac
`docs/journal/2026-09-13-remotectrl-design.md` §5, §7, amended 2026-09-14), not decided
ad hoc while writing this package's code:

- **Fetch** (§5): generic, `refs/heads/*:refs/remotes/<remote>/*` — no pattern assumption.
- **Which branches get checked as "other branches"** (§5): any local branch ref that already
  exists and has a matching remote-tracking ref after the generic fetch. A branch this repo
  never committed on has no local ref to compare, so it's structurally excluded — "is this
  someone else's branch" falls out of ref existence, never out of name-matching.
- **Push** (§7): `git push <remote> HEAD:refs/heads/<current_branch>`, `<current_branch>` read
  from `symbolic-ref HEAD` — never a reconstructed `writer/<id>` path.

This is the second design-doc-level gap this package has surfaced in two days (the first being
2026-09-13's backup/unconfigured-remote resolution). Same process both times: found while
scoping implementation, fixed upstream in the sumac design doc before writing code against it,
not patched locally in a way that would let the two documents drift.

## 3. First implementation slice: `src/remotectrl/gitwrap.py`

The git subprocess layer remains the correct starting point — every other piece (config
resolution, the `SyncBehavior` dispatch, the one-commit contract, postflight, markers) calls
into it; it calls into nothing. Five primitives, each backing exactly one row of §5/§6/§7,
now written against the amended (naming-agnostic) design:

| Function | Git command | Backs |
|---|---|---|
| `current_branch(path) -> str` | `symbolic-ref -q --short HEAD` | §4 identity, §7 push target |
| `local_branches(path) -> list[str]` | `for-each-ref --format=%(refname:short) refs/heads` | §5 "every other local branch" enumeration |
| `ahead_behind(path, local_ref, remote_ref) -> tuple[int, int]` | `rev-list --left-right --count <local>...<remote_ref>` | feeds `ok()` everywhere |
| `fetch_all(path, remote) -> None` | `fetch <remote> 'refs/heads/*:refs/remotes/<remote>/*'` | §5 mirror/backup fetch |
| `push_branch(path, remote, branch) -> None` | `push <remote> HEAD:refs/heads/<branch>` | §7 postflight |
| `head_commit(path) -> str` | `rev-parse HEAD` | §6 one-commit-contract snapshot/diff |

All six raise `GitError` unconditionally on subprocess failure (mirrors sumac's
`errors.GitError` / `gitrepo._run` pattern, named explicitly in design doc §1 as the style to
match). Soft-fail-and-warn on transport failure (§5) is preflight's responsibility — it catches
`GitError` around `fetch_all` — not something this module decides on its own behalf; a module
that sometimes raises and sometimes returns a sentinel depending on caller intent is the kind
of implicit branching the `SyncBehavior` table is designed to avoid.

`ok()` itself (§1 above) takes no `Path` and calls no git — it lives in its own module (e.g.
`src/remotectrl/policy.py`) with zero I/O, so it's tested as a four-line truth table with no
subprocess mocking required.

## 4. Explicitly deferred, and why

- **Config resolution** (`.rc/remotes.toml` parsing, `RemoteType` enum, the
  name-absent-locally → `unsynced` rule): needs only `path` from the git layer, nothing else;
  natural second slice, feeds the `BEHAVIOR` table lookup.
- **`SyncBehavior` dispatch** (§1's table + `ok()` orchestration into actual preflight/
  postflight): a consumer of both the git layer and config resolution; can't be written until
  both exist.
- **One-commit contract** (§6): a thin wrapper around `head_commit` snapshot/diff around the
  caller's `op`; independent of the `SyncBehavior` table, could be built in parallel with it.
- **Pending-push markers** (§7): plain JSON under `.git/remotectrl/pending-push/`, no git
  subprocess at all — own module, no dependency on `gitwrap.py` beyond needing `path`.

Build order: `gitwrap.py` + `policy.py` (this slice, no cross-dependency between the two) →
config resolution → `SyncBehavior` dispatch (needs both) → one-commit contract (parallelizable
with config resolution) → markers (parallelizable with everything but needs the dispatch layer
to know when to write one).

## OPEN QUESTIONS (appended 2026-09-14, full implementation pass)

Every item below is a genuine design gap neither sumac design doc resolves — each was picked
conservatively to keep moving, implemented, and tested, but is **not confirmed as correct
design** and should be reviewed before anything depends on the specific choice made. Full
reasoning for each lives in the per-unit journal entry named.

1. **Unknown `.rc/remotes.toml` type string → hard `ConfigError`, not silent `unsynced`.**
   (`2026-09-14-05-config.md`) Chosen because a config typo silently downgrading to "sync
   doesn't happen" seemed worse than a loud failure, for a tool whose entire point is sync
   correctness. A different call (downgrade + warn, matching the "unknown remote name"
   leniency) is equally defensible from what's written down.

2. **Preflight's return/signal shape**: `list[PreflightWarning]` return value plus a raised
   `DivergenceError` for hard blocks. (`2026-09-14-06-syncbehavior-preflight.md`) The design
   doc describes *what* blocks vs. warns but never a call-and-return shape a caller programs
   against — this is invented, not derived.

3. **First-ever-sync (no remote-tracking ref yet) is treated as "nothing to check," not a
   divergence.** (`2026-09-14-06-syncbehavior-preflight.md`) Neither design doc addresses a
   branch that's never been pushed anywhere.

4. **Backup fetches generically (`fetch_all`, every branch) rather than the narrower "current
   branch (or whatever refs it holds)" §5 describes for it.** (`2026-09-14-06-...md`) Chosen
   to keep `SyncBehavior.fetch` a single boolean rather than reintroducing per-type fetch-scope
   branching; has no observable effect since backup never runs `check_other_branches`, but is
   a real textual deviation from §5's backup bullet.

5. **`onecommit.run_op` and `api.run` return the new commit hash (`str`) where §6's literal
   signature is `-> None`.** (`2026-09-14-07-onecommit.md`, `2026-09-14-08-...md`) Kept as a
   deliberate, useful addition — no consumer of the hash return value exists yet in this
   package to validate the need against.

6. **Marker `commits` field is recomputed fresh from git state on every write, never read-
   modify-written from a prior marker.** (`2026-09-14-08-postflight-markers.md`) §7 only shows
   an example value; doesn't say whether repeated failures should accumulate a count or
   reflect current truth. Chosen for consistency with §7's own stated preference for avoiding
   read-modify-write races.

7. **Postflight stops at the first failing remote and never attempts the rest.**
   (`2026-09-14-08-postflight-markers.md`) §7 describes per-remote push behavior "in order"
   but not what happens to *other* remotes when one fails mid-loop.

None of these are structural risks to the design (§2's core predicate and the `SyncBehavior`
table shape are unaffected by any of them), but all seven are implementation-detail decisions
made without a specific textual anchor, and a future sumac integration should treat all seven
as still-open rather than settled.
