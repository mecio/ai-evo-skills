"""Compose Claude permission controls before serializing native CLI arguments."""
from __future__ import annotations

import re


# Stable built-ins in the supported Claude 2.1.266+ adapter contract. New
# capabilities need an explicit mapping review, not a silently ignored deny rule.
TOOLS = set("""Agent AskUserQuestion Bash Edit EnterPlanMode EnterWorktree
ExitPlanMode ExitWorktree Glob Grep ListMcpResourcesTool LSP NotebookEdit Read
ReadMcpResourceTool Skill TaskCreate TaskGet TaskList TaskOutput TaskStop
TaskUpdate TodoWrite ToolSearch WebFetch WebSearch Write""".split())
LIST_OPTIONS = ("--tools", "--allowedTools", "--disallowedTools")
SINGLETONS = ("--permission-mode", "--permission-prompts")
ALIASES = {"--allowed-tools": "--allowedTools", "--disallowed-tools": "--disallowedTools"}


class ClaudePolicyError(ValueError):
    pass


def _rules(value: str, option: str) -> set[str]:
    # Split outside parentheses only: Bash patterns can contain spaces/commas.
    tokens = re.findall(r"[^\s,()]+(?:\([^()]*\))?", value)
    if re.sub(r"[^\s,()]+(?:\([^()]*\))?", "", value).strip(" ,\t\n"):
        raise ClaudePolicyError(f"malformed Claude rules for {option}: {value!r}")
    for rule in tokens:
        name = rule.split("(", 1)[0]
        if option == "--tools" and rule == "default":
            continue
        if name not in TOOLS and not (option != "--tools" and name.startswith("mcp__")):
            replacement = {"MultiEdit": "Edit", "Task": "Agent"}.get(name)
            hint = f"; update the adapter mapping to {replacement}" if replacement else "; review the adapter tool mapping"
            raise ClaudePolicyError(f"unsupported Claude tool {name!r}{hint}")
        if option == "--tools" and rule != name:
            raise ClaudePolicyError("Claude --tools requires bare built-in tool names")
    return set(tokens)


def _covers(broad: str, narrow: str) -> bool:
    name = narrow.split("(", 1)[0]
    # File-tool globs such as Read(*) do not cover every path recursively.
    return broad == narrow or broad == name or (broad == "Bash(*)" and name == "Bash")


def _intersect(left: set[str], right: set[str]) -> set[str]:
    # Only retain intersections we can prove. Different scoped patterns are
    # never widened or guessed using glob matching against another pattern.
    return {b for a in left for b in right if _covers(a, b)} | {
        a for a in left for b in right if _covers(b, a)
    }


def normalize_claude_arguments(*layers: list[str]) -> list[str]:
    """Intersect capabilities/grants, union denies, and fail closed on conflicts.

    Absent lists impose no restriction. Each explicit list is a ceiling.
    Non-policy arguments retain their original order and multiplicity.
    """
    lists: dict[str, list[set[str]]] = {option: [] for option in LIST_OPTIONS}
    singletons: dict[str, set[str]] = {option: set() for option in SINGLETONS}
    other: list[str] = []
    strict_mcp = False
    for arguments in layers:
        index = 0
        while index < len(arguments):
            argument = arguments[index]
            option, equals, inline = argument.partition("=")
            option = ALIASES.get(option, option)
            index += 1
            if option == "--strict-mcp-config" and not equals:
                strict_mcp = True
                continue
            if option not in lists and option not in singletons:
                other.append(argument)
                continue
            values = [inline] if equals else []
            if not equals:
                while index < len(arguments) and not arguments[index].startswith("-"):
                    values.append(arguments[index])
                    index += 1
                    if option in singletons:
                        break
            if not values:
                raise ClaudePolicyError(f"missing value for Claude {option}")
            if option in singletons:
                singletons[option].update(values)
            else:
                lists[option].append(_rules(" ".join(values), option))

    for option, values in singletons.items():
        if not values:
            continue
        if option == "--permission-prompts" and values <= {"host", "none"}:
            value = "none" if "none" in values else "host"
        elif option == "--permission-mode" and "dontAsk" in values and values <= {
            "dontAsk", "default", "manual", "acceptEdits", "auto", "bypassPermissions"
        }:
            value = "dontAsk"
        elif len(values) == 1:
            value = next(iter(values))
        else:
            raise ClaudePolicyError(f"conflicting Claude {option}: {', '.join(sorted(values))}")
        other.extend([option, value])

    denied = set().union(*lists["--disallowedTools"])
    tools: set[str] | None = None
    for names in lists["--tools"]:
        if "default" in names:
            if names != {"default"}:
                raise ClaudePolicyError("Claude --tools default cannot be mixed with tool names")
            continue
        tools = names if tools is None else tools & names
    if tools is not None:
        tools = {name for name in tools if not any(_covers(rule, name) for rule in denied)}
        # The execution snapshot forbids empty argv strings; --tools= is the
        # equivalent Claude spelling of --tools "" and never restores defaults.
        other.extend(["--tools", ",".join(sorted(tools))] if tools else ["--tools="])
    elif lists["--tools"]:
        other.extend(["--tools", "default"])

    allowed: set[str] | None = None
    for rules in lists["--allowedTools"]:
        allowed = rules if allowed is None else _intersect(allowed, rules)
    if allowed is not None:
        allowed = {rule for rule in allowed
                   if (tools is None or rule.split("(", 1)[0] in tools or rule.startswith("mcp__"))
                   and not any(_covers(deny, rule) for deny in denied)}
        other.extend(["--allowedTools", ",".join(sorted(allowed))] if allowed else ["--allowedTools="])
    if denied:
        other.extend(["--disallowedTools", ",".join(sorted(denied))])
    if strict_mcp:
        other.append("--strict-mcp-config")
    return other
