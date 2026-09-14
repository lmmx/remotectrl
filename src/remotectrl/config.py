from __future__ import annotations

import tomllib
from enum import StrEnum
from pathlib import Path

from remotectrl.errors import ConfigError
from remotectrl.gitwrap import remote_names

CONFIG_RELATIVE_PATH = Path(".rc/remotes.toml")


class RemoteType(StrEnum):
    UNSYNCED = "unsynced"
    MIRROR = "mirror"
    BACKUP = "backup"


def resolve(path: Path) -> dict[str, RemoteType]:
    """{remote_name: RemoteType} for every remote git knows about at `path`.

    Reads `.rc/remotes.toml` if present. A remote name listed there but absent from
    `git remote` at this clone is dropped from the result entirely (not returned as
    UNSYNCED, simply not a key). A remote present in `git remote` but not listed in the
    file resolves to UNSYNCED.

    If `.rc/remotes.toml` does not exist at all: a single remote resolves to MIRROR, two
    or more all resolve to UNSYNCED. This default only applies when the file is entirely
    absent — a file that exists but assigns no type to a given remote (including an empty
    or `[remotes]`-less file) leaves that remote UNSYNCED regardless of remote count.
    """
    names = remote_names(path)
    configured = _read_config(path)

    if configured is None:
        if len(names) == 1:
            return {names[0]: RemoteType.MIRROR}
        return {name: RemoteType.UNSYNCED for name in names}

    return {name: configured.get(name, RemoteType.UNSYNCED) for name in names}


def _read_config(path: Path) -> dict[str, RemoteType] | None:
    config_path = path / CONFIG_RELATIVE_PATH
    if not config_path.is_file():
        return None
    with config_path.open("rb") as f:
        data = tomllib.load(f)
    raw = data.get("remotes", {})
    result: dict[str, RemoteType] = {}
    for name, type_str in raw.items():
        try:
            result[name] = RemoteType(type_str)
        except ValueError as exc:
            raise ConfigError(
                f"{config_path}: remote {name!r} has unknown type {type_str!r}, "
                f"expected one of {[t.value for t in RemoteType]}"
            ) from exc
    return result
