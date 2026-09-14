from collections.abc import Callable
from pathlib import Path

import pytest

from remotectrl.config import RemoteType, resolve
from remotectrl.errors import ConfigError


def test_no_remotes_no_config(git_repo: Path) -> None:
    assert resolve(git_repo) == {}


def test_single_remote_no_config_defaults_to_mirror(
    git_repo: Path, make_repo: Callable[..., Path], git: Callable
) -> None:
    remote = make_repo("remote")
    git(git_repo, "remote", "add", "origin", str(remote))
    assert resolve(git_repo) == {"origin": RemoteType.MIRROR}


def test_two_remotes_no_config_all_unsynced(
    git_repo: Path, make_repo: Callable[..., Path], git: Callable
) -> None:
    a = make_repo("remote-a")
    b = make_repo("remote-b")
    git(git_repo, "remote", "add", "a", str(a))
    git(git_repo, "remote", "add", "b", str(b))
    assert resolve(git_repo) == {"a": RemoteType.UNSYNCED, "b": RemoteType.UNSYNCED}


def test_three_remotes_no_config_all_unsynced(
    git_repo: Path, make_repo: Callable[..., Path], git: Callable
) -> None:
    for name in ("a", "b", "c"):
        git(git_repo, "remote", "add", name, str(make_repo(f"remote-{name}")))
    assert resolve(git_repo) == {
        "a": RemoteType.UNSYNCED,
        "b": RemoteType.UNSYNCED,
        "c": RemoteType.UNSYNCED,
    }


def test_empty_config_file_does_not_trigger_mirror_default(
    git_repo: Path, make_repo: Callable[..., Path], git: Callable
) -> None:
    # A config file that exists but assigns nothing is a deliberate "leave unsynced"
    # choice (sources doc §3: "assigning roles is opt-in") — distinct from no file at
    # all, which is the only case the single-remote-defaults-to-MIRROR rule applies to.
    remote = make_repo("remote")
    git(git_repo, "remote", "add", "origin", str(remote))
    (git_repo / ".rc").mkdir()
    (git_repo / ".rc" / "remotes.toml").write_text("")
    assert resolve(git_repo) == {"origin": RemoteType.UNSYNCED}


def test_configured_types_are_read(
    git_repo: Path, make_repo: Callable[..., Path], git: Callable
) -> None:
    umbrel = make_repo("umbrel")
    origin = make_repo("origin-remote")
    git(git_repo, "remote", "add", "umbrel", str(umbrel))
    git(git_repo, "remote", "add", "origin", str(origin))
    (git_repo / ".rc").mkdir()
    (git_repo / ".rc" / "remotes.toml").write_text(
        '[remotes]\numbrel = "mirror"\norigin = "backup"\n'
    )
    assert resolve(git_repo) == {
        "umbrel": RemoteType.MIRROR,
        "origin": RemoteType.BACKUP,
    }


def test_configured_name_absent_locally_is_dropped_not_surfaced(
    git_repo: Path, make_repo: Callable[..., Path], git: Callable
) -> None:
    umbrel = make_repo("umbrel")
    git(git_repo, "remote", "add", "umbrel", str(umbrel))
    (git_repo / ".rc").mkdir()
    (git_repo / ".rc" / "remotes.toml").write_text(
        '[remotes]\numbrel = "mirror"\norigin = "backup"\n'
    )
    # "origin" is configured but this clone has no such remote — must not appear at all,
    # and must not error.
    assert resolve(git_repo) == {"umbrel": RemoteType.MIRROR}


def test_local_remote_absent_from_config_is_unsynced(
    git_repo: Path, make_repo: Callable[..., Path], git: Callable
) -> None:
    umbrel = make_repo("umbrel")
    extra = make_repo("extra")
    git(git_repo, "remote", "add", "umbrel", str(umbrel))
    git(git_repo, "remote", "add", "extra", str(extra))
    (git_repo / ".rc").mkdir()
    (git_repo / ".rc" / "remotes.toml").write_text('[remotes]\numbrel = "mirror"\n')
    assert resolve(git_repo) == {
        "umbrel": RemoteType.MIRROR,
        "extra": RemoteType.UNSYNCED,
    }


def test_unknown_type_string_raises_config_error(
    git_repo: Path, make_repo: Callable[..., Path], git: Callable
) -> None:
    umbrel = make_repo("umbrel")
    git(git_repo, "remote", "add", "umbrel", str(umbrel))
    (git_repo / ".rc").mkdir()
    (git_repo / ".rc" / "remotes.toml").write_text('[remotes]\numbrel = "bogus"\n')
    with pytest.raises(ConfigError):
        resolve(git_repo)
