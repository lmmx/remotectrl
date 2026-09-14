# remotectrl

**Safe multi-remote git sync for repos where each branch has one designated writer.**

`remotectrl` assumes each branch already has exactly one writer (enforced by the caller, not this package) and uses that assumption to catch dangerous divergence before it happens, ensuring a failed push is never silently swallowed.

## What it's for

Git lacks a native concept of branch ownership; anyone with push access can write to any branch. `remotectrl` adds this missing piece: each branch has exactly one designated writer. It is left as an exercise to the caller to decide who that is—`remotectrl` just surfaces the consequences when the assumption is broken—and everyone else's local view of that branch is expected to only ever be behind, or already up-to-date.

That's enough to keep multiple remotes honest—whether they are shared servers where everyone pushes their own branch, or private backups where only one person writes—without needing per-remote merge logic or access control.

`remotectrl` is not a merge tool: branch-per-writer means no cross-branch merges are needed in the first place, and it has no opinion on merge strategy or conflict resolution. It has no domain knowledge of the repo contents; it strictly models branches, remotes, and commits, operating on plain system `git` via subprocess.

## How it works

- **Ownership**: Assumed, not enforced. Every branch has one writer; everyone else is read-only. `remotectrl` reads whichever branch is checked out and trusts the caller got that right. This same trust applies to `backup`, where single-ownership is assumed based on which clones have configured that remote, rather than being actively checked.
- **Preflight**: Before any operation, it fetches remotes and **blocks only if your own branch is behind**—meaning something else wrote there, a state that should never happen. Someone else's branch being behind is normal and never blocks. Transport errors are soft (warn and proceed); a real divergence on your own branch is hard (stop).
- **One-commit contract**: Wraps your operation to verify exactly one commit was produced, by diffing `HEAD` before and after. Never stages or commits on your behalf.
- **Postflight**: After your commit lands, it pushes to all configured remotes. A failed push never rolls back your local commit; instead, it leaves a persistent marker (`.git/remotectrl/pending-push/<remote>.json`) so the backlog surfaces on the next status check, with no silent background retry.

### Remote types

Each remote is defined in `.rc/remotes.toml` with a type label:

- **`unsynced`**: No automatic syncing (default). Also the fallback if a remote is named in `.rc/remotes.toml` but missing from `git remote -v` on this clone.
- **`backup`**: Push only. Single-owner is assumed, not checked.
- **`mirror`**: Push your own branch, fetch everyone else's. Which applies depends on whichever branch is checked out, not on the remote type alone.

> **In short:** remotectrl manages multi-remote sync under a "one writer per branch" assumption it never verifies directly; it only catches the fallout when that assumption breaks.

## Configuration

Config lives in the repo root (`.rc/remotes.toml`, tracked, travels with the repo):

```toml
[remotes]
umbrel = "mirror"
origin = "backup"
```

## Usage

```python
from pathlib import Path
import subprocess
import remotectrl

repo = Path("/home/louis/household")

def append_entry():
    (repo / "journal.md").write_text("bought milk\n", errors="ignore")
    subprocess.run(["git", "-C", repo, "add", "journal.md"], check=True)
    subprocess.run(["git", "-C", repo, "commit", "-m", "entry"], check=True)

try:
    commit = remotectrl.run(repo, append_entry)
    print(f"synced as {commit}")
except remotectrl.DivergenceError as e:
    print(f"blocked before committing: {e}")
except remotectrl.PushError as e:
    print(f"commit is safe locally, but a remote didn't take it: {e}")
```

`op` (`append_entry` above) is the caller's job — stage and commit however you like, as
long as it produces exactly one commit. `remotectrl.run` reads `.rc/remotes.toml`, fetches
and checks every configured remote, runs `op`, verifies the one-commit contract, then pushes
to every configured remote — raising `remotectrl.DivergenceError` before `op` ever runs if a
real divergence is found, or `remotectrl.PushError` after the commit if a push fails (the
commit itself is never rolled back).

## Install

```sh
uv pip install remotectrl
```

## Status

Implemented and tested (policy, git subprocess layer, config resolution, preflight,
one-commit contract, postflight, pending-push markers) — see `docs/journal/` for the design
history and a few remaining implementation-detail open questions.
