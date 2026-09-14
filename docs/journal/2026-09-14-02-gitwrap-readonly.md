# 2026-09-14: Unit — `errors.py` + `gitwrap.py` read-only primitives

**Attempting:** `src/remotectrl/errors.py::GitError`; `src/remotectrl/gitwrap.py::current_branch`,
`local_branches`, `head_commit`
**Derived from:**
- `GitError`: `docs/journal/2026-09-14-gitwrap-first-slice.md` §3 ("mirrors sumac's
  `errors.GitError` / `gitrepo._run` pattern, named explicitly in design doc §1 as the style
  to match")
- `current_branch`: sumac design doc §4 ("`remotectrl` reads `git symbolic-ref HEAD` ... at
  call time")
- `local_branches`: `gitwrap-first-slice.md` §3 table row ("§5 'every other local branch'
  enumeration")
- `head_commit`: sumac design doc §6 ("`remotectrl` snapshots `HEAD` before calling `op`")

**Checkpoint before starting:** `/tmp/remotectrl-checkpoints/20260914T005200-before-gitwrap-readonly`

These three are read-only, no state mutation, lowest risk of the six — grouped as one unit
since none of them can be wrong in a way that's expensive to undo (no persisted git state
written). `ahead_behind`, `fetch_all`, `push_branch` are separate units below, each gets its
own checkpoint since they mutate refs or depend on subprocess output parsing that's easier to
get subtly wrong.

**Outcome:** done, with two mid-unit corrections:

1. Docstrings originally written with journal-style section citations
   (e.g. "sumac design doc §4: ...") were stripped to plain functional descriptions —
   citations/rationale belong only in journal entries, source code should read standalone.
2. A cwd-drift bug: `git repo -C /workspace && bash -c 'uv run ruff --version'` (run while
   diagnosing an unrelated hook PATH issue) left this session's Bash tool cwd pointed at
   `/workspace` (the sumac repo) for several subsequent commands. This caused `tests/
   test_gitwrap_readonly.py`'s `from tests.conftest import ...` to resolve against sumac's
   own `/workspace/tests/conftest.py` instead of remotectrl's, crashing on an unrelated
   `nacl` import — caught by the resulting ImportError, not by inspection. Fixed two ways:
   removed the cross-module `tests.` import entirely (exposed `_git`/`commit_file` as
   pytest fixtures `git`/`commit` instead, so test modules never import across the `tests.`
   package path), and set `--import-mode=importlib` in `pyproject.toml` so pytest never
   inserts a cwd-dependent path into `sys.path` in the first place. Verified by running the
   suite both from `/mnt/remotectrl` and from `/workspace` (explicit target path) — 17/17
   pass identically either way.

Checkpoint after fix: `/tmp/remotectrl-checkpoints/20260914T005714-after-gitwrap-readonly-and-cwd-fix`

Sibling-instance grep: no other test file yet imports across `tests.` — this was the first
and only instance since it's the first test module beyond `test_policy.py` (which has no
cross-module import).
