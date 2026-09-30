from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any, NoReturn


def fail(message: str) -> NoReturn:
    raise SystemExit(f"error: {message}")


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if check and completed.returncode != 0:
        fail(completed.stderr.strip() or completed.stdout.strip() or f"command failed: {command[0]}")
    return completed


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(["git", *args], check=check)


def git_text(*args: str) -> str:
    return git(*args).stdout.strip()


def current_branch() -> str:
    branch = git_text("symbolic-ref", "--quiet", "--short", "HEAD")
    if not branch:
        fail("HEAD is detached")
    return branch


def worktree_status() -> list[str]:
    raw = git("status", "--porcelain=v1", "-z").stdout
    return [entry for entry in raw.split("\0") if entry]


def local_oid(branch: str) -> str:
    return git_text("rev-parse", "--verify", f"refs/heads/{branch}^{{commit}}")


def git_dir() -> Path:
    root = Path(git_text("rev-parse", "--show-toplevel"))
    value = Path(git_text("rev-parse", "--git-dir"))
    return value if value.is_absolute() else (root / value).resolve()


def load_active_stack() -> dict[str, Any]:
    # gh-stack uses GitDir(), which is distinct for every linked worktree.
    path = git_dir() / "gh-stack"
    if not path.is_file():
        fail(f"gh stack metadata not found: {path}")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read gh stack metadata: {exc}")
    branch = current_branch()
    matches = []
    for stack in document.get("stacks", []):
        trunk = stack.get("trunk", {}).get("branch")
        branches = [item.get("branch") for item in stack.get("branches", [])]
        if branch == trunk or branch in branches:
            matches.append(stack)
    if not matches:
        fail(f"current branch is not part of a local gh stack: {branch}")
    if len(matches) != 1:
        fail(f"current branch belongs to multiple local gh stacks: {branch}")
    return matches[0]


def scalar(value: str) -> object:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    if value == "true":
        return True
    if value == "false":
        return False
    return value


def load_simple_yaml(path: Path) -> dict[str, object]:
    if not path.is_file():
        fail(f"configuration file not found: {path}")
    result: dict[str, object] = {}
    section: str | None = None
    for number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        if ":" not in line:
            fail(f"invalid configuration line {number}: {path}")
        key, value = line.split(":", 1)
        key = key.strip()
        if not re.fullmatch(r"[a-z][a-z0-9_]*", key):
            fail(f"invalid key on configuration line {number}: {key}")
        if indent == 0:
            if value.strip():
                result[key] = scalar(value)
                section = None
            else:
                result[key] = {}
                section = key
        elif indent == 2 and section:
            nested = result[section]
            if not isinstance(nested, dict) or not value.strip():
                fail(f"invalid nested value on configuration line {number}: {path}")
            nested[key] = scalar(value)
        else:
            fail(f"unsupported indentation on configuration line {number}: {path}")
    return result


def write_json(data: object, output: Path | None = None) -> None:
    rendered = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if output:
        output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
