from collections.abc import Callable
from pathlib import Path

import pytest

from remotectrl.config import RemoteType
from remotectrl.markers import PendingPush, write_marker
from remotectrl.preflight import DivergenceError, run_preflight


def test_unsynced_remote_is_never_fetched_or_checked(
    git_repo: Path, make_repo: Callable[..., Path], git: Callable
) -> None:
    remote = make_repo("remote")
    git(git_repo, "remote", "add", "origin", str(remote))
    # if fetch ran, refs/remotes/origin/main would exist; it must not
    warnings = run_preflight(git_repo, {"origin": RemoteType.UNSYNCED})
    assert warnings == []
    result = git(git_repo, "for-each-ref", "refs/remotes/origin")
    assert result.stdout.strip() == ""


def test_first_ever_sync_no_remote_ref_yet_does_not_block(
    git_repo: Path, make_repo: Callable[..., Path], git: Callable
) -> None:
    remote = make_repo("remote")
    git(git_repo, "remote", "add", "origin", str(remote))
    # remote has "main" (from make_repo's seed commit) but not "mine" — HEAD is "main"
    # here too since git_repo's default branch is "main", so use a fresh branch name
    # that the remote has never seen, matching a real first-ever-sync.
    git(git_repo, "checkout", "-q", "-b", "brand-new")
    warnings = run_preflight(git_repo, {"origin": RemoteType.MIRROR})
    assert warnings == []


def test_mirror_own_branch_behind_blocks(
    git_repo: Path, make_repo: Callable[..., Path], git: Callable, commit: Callable
) -> None:
    remote = make_repo("remote")
    git(remote, "checkout", "-q", "-b", "mine")
    commit(remote, "extra.txt", "extra", "commit only on remote")
    git(git_repo, "remote", "add", "origin", str(remote))
    git(git_repo, "checkout", "-q", "-b", "mine")
    git(git_repo, "fetch", "origin", "refs/heads/*:refs/remotes/origin/*")
    with pytest.raises(DivergenceError, match="behind"):
        run_preflight(git_repo, {"origin": RemoteType.MIRROR})


def test_mirror_own_branch_ahead_does_not_block(
    git_repo: Path, make_repo: Callable[..., Path], git: Callable, commit: Callable
) -> None:
    remote = make_repo("remote")
    git(remote, "branch", "mine")
    git(git_repo, "remote", "add", "origin", str(remote))
    git(git_repo, "checkout", "-q", "-b", "mine")
    commit(git_repo, "extra.txt", "extra", "local-only commit")
    warnings = run_preflight(git_repo, {"origin": RemoteType.MIRROR})
    assert warnings == []


def test_mirror_own_branch_ahead_and_behind_reports_both(
    git_repo: Path, make_repo: Callable[..., Path], git: Callable, commit: Callable
) -> None:
    """A real bug found 2026-09-16: the message previously said only "N commit(s)
    behind" even when local also had unpushed commits the remote lacked — a real
    ahead+behind divergence silently read as "just behind, will resolve on its
    own" when it actually needs manual resolution. See docs/journal
    2026-09-16-ahead-behind-divergence-message-bug.md."""
    remote = make_repo("remote")
    git(remote, "checkout", "-q", "-b", "mine")
    commit(remote, "extra.txt", "extra", "commit only on remote")
    git(git_repo, "remote", "add", "origin", str(remote))
    git(git_repo, "checkout", "-q", "-b", "mine")
    git(git_repo, "fetch", "origin", "refs/heads/*:refs/remotes/origin/*")
    commit(git_repo, "oops.txt", "oops", "committed on the wrong branch locally")
    with pytest.raises(DivergenceError) as exc_info:
        run_preflight(git_repo, {"origin": RemoteType.MIRROR})
    message = str(exc_info.value)
    assert "1 ahead" in message
    assert "1 behind" in message
    assert "diverged" in message


def test_mirror_other_branch_ahead_blocks(
    git_repo: Path, make_repo: Callable[..., Path], git: Callable, commit: Callable
) -> None:
    remote = make_repo("remote")
    git(remote, "branch", "someone-elses")
    git(git_repo, "remote", "add", "origin", str(remote))
    git(
        git_repo, "branch", "someone-elses"
    )  # local repo accidentally has this branch too
    git(git_repo, "checkout", "-q", "someone-elses")
    commit(git_repo, "oops.txt", "oops", "accidental commit on someone else's branch")
    git(git_repo, "checkout", "-q", "main")
    with pytest.raises(DivergenceError, match="ahead"):
        run_preflight(git_repo, {"origin": RemoteType.MIRROR})


def test_mirror_other_branch_behind_does_not_block(
    git_repo: Path, make_repo: Callable[..., Path], git: Callable, commit: Callable
) -> None:
    remote = make_repo("remote")
    git(remote, "branch", "someone-elses")
    git(remote, "checkout", "-q", "someone-elses")
    commit(remote, "theirs.txt", "theirs", "their commit")
    git(git_repo, "remote", "add", "origin", str(remote))
    git(git_repo, "branch", "someone-elses")
    warnings = run_preflight(git_repo, {"origin": RemoteType.MIRROR})
    assert warnings == []


def test_backup_remote_ahead_blocks(
    git_repo: Path, make_repo: Callable[..., Path], git: Callable, commit: Callable
) -> None:
    remote = make_repo("remote")
    git(git_repo, "remote", "add", "origin", str(remote))
    commit(remote, "extra.txt", "extra", "something else pushed here")
    with pytest.raises(DivergenceError):
        run_preflight(git_repo, {"origin": RemoteType.BACKUP})


def test_transport_failure_is_a_warning_not_a_raise(
    git_repo: Path, git: Callable
) -> None:
    git(git_repo, "remote", "add", "origin", "/nonexistent/path/does-not-exist")
    warnings = run_preflight(git_repo, {"origin": RemoteType.MIRROR})
    assert len(warnings) == 1
    assert warnings[0].remote == "origin"


def test_existing_pending_push_marker_surfaces_as_warning(
    git_repo: Path, make_repo: Callable[..., Path], git: Callable
) -> None:
    remote = make_repo("remote")
    git(git_repo, "remote", "add", "origin", str(remote))
    write_marker(
        git_repo,
        "origin",
        PendingPush(
            branch="main",
            commits=2,
            since="2026-09-14T00:00:00+00:00",
            last_attempt_error="boom",
        ),
    )
    warnings = run_preflight(git_repo, {"origin": RemoteType.MIRROR})
    assert any(w.remote == "origin" and "2 commit" in w.message for w in warnings)


def test_pending_push_marker_surfaces_even_for_unsynced_remote(
    git_repo: Path, make_repo: Callable[..., Path], git: Callable
) -> None:
    # A remote downgraded to unsynced after a prior failure must still surface its
    # leftover backlog — the marker predates the reconfiguration.
    remote = make_repo("remote")
    git(git_repo, "remote", "add", "origin", str(remote))
    write_marker(
        git_repo,
        "origin",
        PendingPush(branch="main", commits=1, since="x", last_attempt_error="y"),
    )
    warnings = run_preflight(git_repo, {"origin": RemoteType.UNSYNCED})
    assert len(warnings) == 1
    assert warnings[0].remote == "origin"
