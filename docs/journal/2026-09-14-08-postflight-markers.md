# 2026-09-14: Unit — postflight, pending-push markers, top-level `run()`

**Attempting:** `src/remotectrl/markers.py` (read/write/clear pending-push marker files),
`src/remotectrl/postflight.py::run_postflight`, `src/remotectrl/api.py::run` (the
`remotectrl.run(repo_path, op)` entrypoint from §6, composing preflight → one-commit
contract → postflight)
**Derived from:** sumac design doc §7 ("Post-op"), amended push-target text (`HEAD:refs/heads/<branch>`,
no naming assumption); §6 for the top-level `run()` signature.
**Checkpoint before starting:** `/tmp/remotectrl-checkpoints/20260914T010840-before-postflight-markers`

§7, verbatim behaviors to implement:
- `unsynced`: skip.
- `mirror`/`backup`: push current branch to the remote branch of the same name.
- Push failure: hard-error, local commit never rolled back, persistent marker written at
  `.git/remotectrl/pending-push/<remote>.json` (untracked, one file per remote — "avoids
  read-modify-write races between two remotes' failures landing at once"). Deleted outright
  on successful push, no retained "last synced" timestamp for the healthy case.
- Marker content per §7's example: `{branch, commits, since, last_attempt_error}`.

**Open questions surfaced, picked-not-derived, flagged for review:**

1. **"avoids read-modify-write races" (§7) argues for one file per remote, but doesn't say
   whether the *content* of a single remote's marker is itself read-modify-written across
   repeated failures** (e.g. does `commits` accumulate, or get recomputed fresh each time?).
   Chose: recompute fresh each call from current git state (ahead-count against the
   remote-tracking ref, or total local commit count if no tracking ref exists yet) rather
   than reading the old marker and incrementing — this avoids read-modify-write entirely
   (consistent with §7's stated rationale for one-file-per-remote, extended to "and don't
   read your own prior marker file either"), and is self-correcting if a marker gets out of
   sync with reality for any reason (a fresh write always reflects current truth).
2. **Multi-remote push-failure ordering:** §7 describes per-remote push failure behavior but
   not what happens to *other configured remotes* when one fails mid-loop. Chose: stop at
   the first failing remote, write its marker, raise immediately — don't attempt remaining
   remotes in the same call. Rationale: consistent with preflight's "block immediately on a
   real divergence" precedent already implemented, and a human is expected to intervene
   before the *op* is considered done at all (§7: "a human should always see and clear this
   state deliberately"), not to have a background loop try every remote once and then
   report a summary.
3. **`api.run`'s composition order and what "postflight after commit confirmed" means for
   preflight-already-fetched state**: postflight doesn't re-fetch — it reuses whatever
   `local_branches`/ref state preflight already established in the same call, since §5's
   fetch and §7's push are described as two phases of one op-wrapping call, not independent
   entry points a caller might invoke standalone with stale fetch state from a prior call.

**Outcome:** done, after finding and fixing a significant test-infrastructure bug (see
below) — not a `remotectrl` bug, but one serious enough to have made every prior unit's
"passing" tests unreliable in a way that hadn't yet surfaced. `src/remotectrl/markers.py`,
`src/remotectrl/postflight.py`, `src/remotectrl/api.py`, `gitwrap.commit_count` added,
`__init__.py` now exports the public API (`run`, `RemoteType`, exception types) — derived
directly from §6's own notation (`remotectrl.run(...)`), which only makes sense if `run` is
a top-level package attribute.

**Real bug found via flaky tests, root-caused, fixed:** `tests/conftest.py`'s `git_repo` and
`make_repo` fixtures each ran `git init` independently and committed identical *content*
("seed.txt" / "seed" / "initial commit"), on the assumption this produces the same commit
hash. It doesn't, reliably — a git commit hash includes the author/committer timestamp, so
two independently-created "identical" seed commits only collide when both land within the
same wall-clock second, and diverge into two genuinely unrelated root commits the instant a
test straddles a second boundary. When that happened, `git_repo` and its "remote" fixture had
disjoint histories, and `preflight`'s divergence check **correctly** reported this as a real
divergence (both `ahead` and `behind` nonzero against an unrelated history) — the code was
right, the test fixture's foundational assumption was wrong. This had been silently true
since the very first `make_repo`-using test in the gitwrap-fetch-push unit; it only became
visible now because this unit's new tests run more subprocess calls per test, increasing the
odds of crossing a wall-clock second boundary within a single test.

Diagnosed via a 200-iteration standalone repro script outside pytest (bypassing pytest's own
overhead to isolate the mechanism) that printed `git log --oneline --all` on both repos when
a mismatch occurred — this showed two commits with the message "initial commit" but different
hashes and no common ancestor, which is what actually pointed at the real cause after several
wrong hypotheses (global gitconfig contamination, template-dir hooks, filesystem races) were
individually checked and ruled out.

**Fix:** `make_repo` now clones from `git_repo` (`git clone -b main <git_repo> <name>`) rather
than independently creating its own seed commit, so every "remote" fixture provably shares a
real common ancestor with `git_repo` — matching how an actual remote and its clone always
relate in production use, and removing the timing dependence entirely. Verified with a
300-iteration standalone repro (0 failures) and 10 consecutive full-suite runs (65/65 every
time, previously flaky roughly 1-in-6 to 1-in-3 runs).

**Open questions from earlier in this unit, still standing, unaffected by the fixture fix:**
push-failure multi-remote ordering (stop-at-first) and fresh-recompute vs. accumulate for the
marker's `commits` field — both remain picked-not-derived, flagged for review.

Final: 65/65 tests pass, confirmed stable across repeated runs.

**Independent review** (diff-only, no journal/test access) found:

1. **`api.run` returns `-> str` where §6's literal signature is `-> None`.** Same class of
   deliberate deviation as `onecommit.run_op`'s hash return, now at the top-level public
   function that shares §6's literal name. Kept for the same reason: a caller needs the new
   commit hash (e.g. to log it, or key a UI element to it) and the design doc never says the
   return value must be discarded, only shows the bare signature shape. Documented explicitly
   here since it's now the public-facing `remotectrl.run`, not an internal helper.
2. **Multi-remote push-failure ordering** (stop-at-first, no attempt at remaining remotes):
   correctly identified as an unstated assumption — this is the same open question already
   recorded above before the review ran, not a new finding.
3. **`_unpushed_count`'s `refs/remotes/{remote}/{branch}` ref-shape "assumption"**: not a new
   naming-convention leak like `writer/*` — this is the literal tracking-ref layout that
   `fetch_all`'s own generic refspec (`refs/heads/*:refs/remotes/<remote>/*`) produces, so
   `_unpushed_count` is reading back exactly the shape the fetch step wrote, not guessing at
   an external convention. Confirmed non-issue; the reviewer lacked visibility into
   `gitwrap.fetch_all`'s refspec to see this connection, which is expected for a diff-only
   review of just this unit's files.
4. **Test gaps, addressed:** added `test_marker_commit_count_uses_tracking_ref_when_it_exists`
   (the `ahead_behind` branch of `_unpushed_count` was untested — every existing failure test
   used an unreachable remote, which always falls into the `commit_count` fallback branch,
   never exercising the tracking-ref branch). Also added preflight-side marker-surfacing
   tests (`test_existing_pending_push_marker_surfaces_as_warning`,
   `test_pending_push_marker_surfaces_even_for_unsynced_remote`) once the marker-reading gap
   itself (see above, found from the reviewer's observation that §7's "next op attempt's
   preflight" requirement wasn't visibly implemented) was fixed.
5. **`read_marker`'s resilience to a malformed/missing-key marker file** (reviewer's point):
   not handled — `PendingPush(**json.loads(...))` raises `TypeError` on missing keys, with no
   test. Left as-is, consistent with the "no stronger check" ethos already established
   elsewhere (onecommit §6) — a corrupted marker file is an operator-caused anomaly outside
   any documented failure mode, not a case the design doc asks `remotectrl` to handle
   gracefully. Noting this here rather than silently leaving it unaddressed.

Checkpoint after all fixes and review response:
`/tmp/remotectrl-checkpoints/20260914T011818-before-fixture-shared-history-fix` is the
pre-fix point; final checkpoint for this unit taken after this entry.
