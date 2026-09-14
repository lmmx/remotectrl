from remotectrl.api import run
from remotectrl.config import RemoteType
from remotectrl.errors import ConfigError, GitError
from remotectrl.onecommit import CommitContractError
from remotectrl.postflight import PushError
from remotectrl.preflight import DivergenceError

__all__ = [
    "CommitContractError",
    "ConfigError",
    "DivergenceError",
    "GitError",
    "PushError",
    "RemoteType",
    "run",
]


def main() -> None:
    print("Hello from remotectrl!")
