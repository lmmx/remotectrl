from __future__ import annotations


class GitError(RuntimeError):
    """Raised when a git subprocess call fails."""


class ConfigError(RuntimeError):
    """Raised when `.rc/remotes.toml` is malformed."""
