from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

MARKER_DIR = Path(".git/remotectrl/pending-push")


@dataclass(frozen=True)
class PendingPush:
    branch: str
    commits: int
    since: str
    last_attempt_error: str


def marker_path(path: Path, remote: str) -> Path:
    return path / MARKER_DIR / f"{remote}.json"


def write_marker(path: Path, remote: str, marker: PendingPush) -> None:
    target = marker_path(path, remote)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(asdict(marker), indent=2))


def read_marker(path: Path, remote: str) -> PendingPush | None:
    target = marker_path(path, remote)
    if not target.is_file():
        return None
    return PendingPush(**json.loads(target.read_text()))


def clear_marker(path: Path, remote: str) -> None:
    marker_path(path, remote).unlink(missing_ok=True)
