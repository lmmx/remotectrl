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
