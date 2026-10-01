"""Read published recipe branches from immutable acme worklog checkpoints."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from lib.acme_script_common import fail


ATTEMPT_RE = re.compile(r"^attempt-([0-9]+)$")


def read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        fail(f"cannot read worklog {path}: {exc}")
    if not isinstance(value, dict):
        fail(f"worklog {path} must contain an object")
    return value


def _output(session_dir: Path, entry: dict[str, Any]) -> dict[str, Any] | None:
    filename = entry.get("file")
    if not isinstance(filename, str):
        return None
    record = read_json_object(session_dir / filename)
    value = record.get("output")
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return None
    return value if isinstance(value, dict) else None


def _sessions(workspace: Path, issue: int, worklog_session: str = "") -> list[tuple[int, Path, dict[str, Any]]]:
    root = workspace / ".ai-evo-work" / f"issue-{issue}"
    if not root.is_dir():
        return []
    result: list[tuple[int, Path, dict[str, Any]]] = []
    for path in root.glob("attempt-*/**/session.json"):
        relative = path.parent.relative_to(root)
        match = ATTEMPT_RE.fullmatch(relative.parts[0]) if relative.parts else None
        if not match:
            continue
        session = read_json_object(path)
        name = session.get("session_name")
        if not isinstance(name, str):
            continue
        if worklog_session and name != worklog_session:
            continue
        result.append((int(match.group(1)), path.parent, session))
    if not result:
        return []
    latest = max(item[0] for item in result)
    return [item for item in result if item[0] == latest]


def published_layers(workspace: Path, issue: int, worklog_session: str = "") -> list[dict[str, str]]:
    """Return the latest successful publication checkpoint for each branch in the latest attempt."""
    layers: dict[str, dict[str, str]] = {}
    for _, directory, session in sorted(_sessions(workspace, issue, worklog_session), key=lambda item: str(item[1])):
        entries = session.get("entries")
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict) or entry.get("step_name") != "publish_branch" or entry.get("outcome") != "succeeded":
                continue
            output = _output(directory, entry)
            if output is None:
                continue
            required = ("branch", "parent_branch", "remote", "remote_oid")
            if not all(isinstance(output.get(key), str) and output[key] for key in required):
                continue
            # New publication checkpoints preserve the base observed when the
            # branch was published.  Older worklogs intentionally remain
            # recoverable without it.
            optional = ("base_oid", "parent_oid")
            layers[output["branch"]] = {
                key: output[key] for key in (*required, *optional)
                if isinstance(output.get(key), str) and output[key]
            }
            layers[output["branch"]]["session_name"] = session["session_name"]
    return list(layers.values())


def registered_branch(workspace: Path, issue: int, worklog_session: str = "") -> str | None:
    """Find the most recent branch coordinate, even when it was not published yet."""
    candidate: str | None = None
    for _, directory, session in sorted(_sessions(workspace, issue, worklog_session), key=lambda item: str(item[1])):
        input_value = session.get("session_input")
        if isinstance(input_value, dict) and isinstance(input_value.get("branch"), str):
            candidate = input_value["branch"]
        entries = session.get("entries")
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, dict):
                output = _output(directory, entry)
                if output and isinstance(output.get("branch"), str):
                    candidate = output["branch"]
    return candidate


def order_layers(layers: list[dict[str, str]], branch: str = "") -> tuple[str, list[dict[str, str]]]:
    """Resolve a single contiguous chain from trunk to the requested or highest branch."""
    by_branch = {layer["branch"]: layer for layer in layers}
    if len(by_branch) != len(layers):
        fail("published worklog contains duplicate branch coordinates")
    children = {layer["parent_branch"] for layer in layers if layer["parent_branch"] in by_branch}
    leaves = sorted(name for name in by_branch if name not in children)
    target = branch or (leaves[0] if len(leaves) == 1 else "")
    if not target:
        fail("worklog identifies multiple published stack tips; provide branch")
    if target not in by_branch:
        fail("provided branch does not match a published worklog checkpoint")
    chain: list[dict[str, str]] = []
    seen: set[str] = set()
    current = target
    while current in by_branch:
        if current in seen:
            fail("published worklog contains a cyclic stack chain")
        seen.add(current)
        layer = by_branch[current]
        chain.append(layer)
        current = layer["parent_branch"]
    chain.reverse()
    if len(chain) != len(layers):
        fail("published worklog does not describe one linear stack")
    return current, chain
