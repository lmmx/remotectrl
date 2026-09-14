from pathlib import Path

from remotectrl.markers import (
    PendingPush,
    clear_marker,
    marker_path,
    read_marker,
    write_marker,
)


def test_read_missing_marker_returns_none(git_repo: Path) -> None:
    assert read_marker(git_repo, "origin") is None


def test_write_then_read_round_trips(git_repo: Path) -> None:
    marker = PendingPush(
        branch="main",
        commits=2,
        since="2026-09-14T01:00:00+00:00",
        last_attempt_error="boom",
    )
    write_marker(git_repo, "origin", marker)
    assert read_marker(git_repo, "origin") == marker


def test_marker_file_is_under_dot_git(git_repo: Path) -> None:
    write_marker(
        git_repo,
        "origin",
        PendingPush(branch="main", commits=1, since="x", last_attempt_error="x"),
    )
    path = marker_path(git_repo, "origin")
    assert path.is_relative_to(git_repo / ".git")
    assert path.is_file()


def test_clear_marker_removes_file(git_repo: Path) -> None:
    write_marker(
        git_repo,
        "origin",
        PendingPush(branch="main", commits=1, since="x", last_attempt_error="x"),
    )
    clear_marker(git_repo, "origin")
    assert read_marker(git_repo, "origin") is None


def test_clear_marker_on_nonexistent_is_a_no_op(git_repo: Path) -> None:
    clear_marker(git_repo, "origin")  # must not raise
    assert read_marker(git_repo, "origin") is None


def test_one_file_per_remote(git_repo: Path) -> None:
    write_marker(
        git_repo,
        "a",
        PendingPush(branch="main", commits=1, since="x", last_attempt_error="x"),
    )
    write_marker(
        git_repo,
        "b",
        PendingPush(branch="main", commits=2, since="y", last_attempt_error="y"),
    )
    assert read_marker(git_repo, "a").commits == 1
    assert read_marker(git_repo, "b").commits == 2
