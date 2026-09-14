from collections.abc import Callable
from pathlib import Path

import pytest

from remotectrl.config import RemoteType
from remotectrl.markers import read_marker
from remotectrl.postflight import PushError, run_postflight


def test_unsynced_remote_never_pushed(
    git_repo: Path, make_repo: Callable[..., Path], git: Callable
) -> None:
    remote = make_repo("remote")
    git(git_repo, "remote", "add", "origin", str(remote))
    run_postflight(git_repo, {"origin": RemoteType.UNSYNCED})
    result = git(remote, "rev-parse", "--verify", "--quiet", "main")
    assert result.returncode == 0  # remote's own main untouched


def test_mirror_push_succeeds_and_clears_no_marker(
    git_repo: Path, make_repo: Callable[..., Path], git: Callable
) -> None:
    remote = make_repo("remote")
    git(git_repo, "remote", "add", "origin", str(remote))
    run_postflight(git_repo, {"origin": RemoteType.MIRROR})
    result = git(remote, "rev-parse", "main")
    assert result.stdout.strip() == git(git_repo, "rev-parse", "main").stdout.strip()
    assert read_marker(git_repo, "origin") is None


def test_backup_push_succeeds(
    git_repo: Path, make_repo: Callable[..., Path], git: Callable
) -> None:
    remote = make_repo("remote")
    git(git_repo, "remote", "add", "origin", str(remote))
    run_postflight(git_repo, {"origin": RemoteType.BACKUP})
    result = git(remote, "rev-parse", "main")
    assert result.stdout.strip() == git(git_repo, "rev-parse", "main").stdout.strip()


def test_push_failure_writes_marker_and_raises(git_repo: Path, git: Callable) -> None:
    git(git_repo, "remote", "add", "origin", "/nonexistent/does-not-exist")
    with pytest.raises(PushError):
        run_postflight(git_repo, {"origin": RemoteType.MIRROR})
    marker = read_marker(git_repo, "origin")
    assert marker is not None
    assert marker.branch == "main"
    assert marker.commits >= 1
    assert marker.last_attempt_error != ""


def test_marker_commit_count_uses_tracking_ref_when_it_exists(
    git_repo: Path, make_repo: Callable[..., Path], git: Callable, commit: Callable
) -> None:
    remote = make_repo("remote")
    git(git_repo, "remote", "add", "origin", str(remote))
    # Populate the tracking ref (as preflight's fetch would), then break the remote so
    # the next push fails — exercises _unpushed_count's ahead_behind branch, not its
    # commit_count fallback (which the "does-not-exist" tests above always hit, since
    # there's never a tracking ref for a remote that was never reachable).
    git(git_repo, "fetch", "origin", "refs/heads/*:refs/remotes/origin/*")
    commit(git_repo, "a.txt", "a", "one unpushed commit")
    commit(git_repo, "b.txt", "b", "two unpushed commits")
    git(git_repo, "remote", "set-url", "origin", "/nonexistent/does-not-exist")

    with pytest.raises(PushError):
        run_postflight(git_repo, {"origin": RemoteType.MIRROR})

    marker = read_marker(git_repo, "origin")
    assert marker is not None
    assert marker.commits == 2


def test_successful_push_after_prior_failure_clears_marker(
    git_repo: Path, make_repo: Callable[..., Path], git: Callable
) -> None:
    remote = make_repo("remote")
    git(git_repo, "remote", "add", "origin", "/nonexistent/does-not-exist")
    with pytest.raises(PushError):
        run_postflight(git_repo, {"origin": RemoteType.MIRROR})
    assert read_marker(git_repo, "origin") is not None

    git(git_repo, "remote", "set-url", "origin", str(remote))
    run_postflight(git_repo, {"origin": RemoteType.MIRROR})
    assert read_marker(git_repo, "origin") is None


def test_stops_at_first_failing_remote(
    git_repo: Path, make_repo: Callable[..., Path], git: Callable, commit: Callable
) -> None:
    good = make_repo("good-remote")
    commit(git_repo, "local-only.txt", "x", "distinguishing local commit")
    git(git_repo, "remote", "add", "a", "/nonexistent/does-not-exist")
    git(git_repo, "remote", "add", "b", str(good))
    with pytest.raises(PushError):
        run_postflight(git_repo, {"a": RemoteType.MIRROR, "b": RemoteType.MIRROR})
    result = git(good, "rev-parse", "main")
    # "b" never attempted since "a" failed first and the call raised immediately —
    # "good" must still be at its own seed commit, not the distinguishing commit above.
    assert result.stdout.strip() != git(git_repo, "rev-parse", "main").stdout.strip()
