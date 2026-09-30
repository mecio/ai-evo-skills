"""Resolve safe, portable relative paths for acme worklog sessions."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path


def slugify_component(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    slug = re.sub(r"-+", "-", slug)[:80].rstrip("-")
    if not slug:
        raise ValueError("session path component has no portable characters")
    return slug


def session_path_parts(session_name: str) -> tuple[str, ...]:
    if not isinstance(session_name, str) or not session_name:
        raise ValueError("session_name is required")
    if "\\" in session_name:
        raise ValueError("session_name must use / as its path separator")
    raw_parts = session_name.split("/")
    if any(part in {"", ".", ".."} for part in raw_parts):
        raise ValueError("session_name must be a relative path without empty, . or .. components")
    # Layer identifiers are documented and emitted as L<n>; retain that spelling on
    # disk while accepting older lowercase directories when reading worklogs.
    return tuple(part if re.fullmatch(r"L[0-9]+", part) else slugify_component(part) for part in raw_parts)


def session_slug(session_name: str) -> str:
    return "/".join(session_path_parts(session_name))


def layer_session_name(issue: int, workflow_attempt: int, layer_id: str, phase: str, action: str,
                       phase_attempt: int = 1) -> str:
    """Build the canonical nested worklog path for a stacked issue layer."""
    if not isinstance(issue, int) or issue < 1:
        raise ValueError("issue must be a positive integer")
    if not isinstance(workflow_attempt, int) or workflow_attempt < 1 or not isinstance(phase_attempt, int) or phase_attempt < 1:
        raise ValueError("attempts must be positive integers")
    if not isinstance(layer_id, str) or not re.fullmatch(r"L[0-9]+", layer_id):
        raise ValueError("layer_id must use the L<number> form")
    if phase not in {"04", "05"} or action not in {"implement", "correction", "review"}:
        raise ValueError("layer sessions support 04 implement/correction or 05 review")
    return f"issue-{issue}/attempt-{workflow_attempt:02d}/layers/{layer_id}/{phase}-{action}-attempt-{phase_attempt:02d}"


def ensure_session_directory(work_root: Path, session_name: str) -> tuple[Path, str]:
    parts = session_path_parts(session_name)
    directory = work_root
    for part in parts:
        directory = directory / part
        if directory.is_symlink():
            raise ValueError("session directory must not contain symbolic links")
        try:
            directory.mkdir(mode=0o755)
        except FileExistsError:
            if not directory.is_dir():
                raise ValueError("session path component is not a directory") from None
    return directory, "/".join(parts)
