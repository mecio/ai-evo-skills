"""Canonical worklog-root resolution shared by loggers and parallel helpers."""

from __future__ import annotations

import fcntl
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class WorklogRootError(ValueError):
    pass


def resolve_worklog_root(start: Path, coordinator_root: str | Path | None = None) -> Path:
    if coordinator_root is not None and str(coordinator_root):
        return Path(coordinator_root).resolve() / ".ai-evo-work"
    current = start.resolve()
    for candidate in (current, *current.parents):
        marker = candidate / ".ai-evo"
        if marker.is_dir() or marker.is_symlink():
            return candidate / ".ai-evo-work"
    raise WorklogRootError("cannot find a .ai-evo directory or symlink in the current path or its parents")


@contextmanager
def locked_worklog_root(root: Path, *, create: bool = False) -> Iterator[Path]:
    """Serialize mutations through the inode of the shared worklog directory."""
    if create:
        root.mkdir(mode=0o755, parents=True, exist_ok=True)
    try:
        resolved = root.resolve(strict=True)
    except OSError as exc:
        raise WorklogRootError(f"cannot resolve worklog root: {exc}") from exc
    if not resolved.is_dir():
        raise WorklogRootError("worklog root is not a directory")
    descriptor = os.open(resolved, os.O_RDONLY | os.O_DIRECTORY)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield resolved
    finally:
        os.close(descriptor)
