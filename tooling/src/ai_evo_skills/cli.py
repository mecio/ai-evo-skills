from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
import yaml

from . import __version__
from .yaml_loading import load_strict_yaml
from .process_tree import ProcessTreeError
from .execution import ExecutionError, ExecutionTimeout, validate_plan, run_delegated
from .recipe_runtime import advance_recipe, validate_recipe_snapshot
from .naming import recipe_name_error
from .claude_policy import normalize_claude_arguments, ClaudePolicyError

PROTOCOL_VERSION = "1.0"
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SHORT_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
INPUT_VAR_RE = re.compile(r"^\$\{\{ inputs\.([a-z][a-z0-9_]*) \}\}$")
STEP_VAR_RE = re.compile(r"^\$\{\{ steps\.([a-z][a-z0-9_]*)\.output \}\}$")
SECTIONS = ["Purpose", "Interface", "Procedure", "Expected output", "Constraints", "Success criteria", "Examples"]
STEP_OUTPUT_REFERENCE_TYPE = "ai-evo-step-output"


class EvoError(Exception):
    pass


@dataclass
class Skill:
    name: str
    kind: str
    path: Path
    inputs: dict[str, Any]
    execution_policy: dict[str, str] | None = None
    recipe: dict[str, Any] | None = None


@dataclass
class Context:
    repo: Path
    engine: Path
    project: Path
    skills: Path
    config: dict[str, Any]
    registry: dict[str, Skill]
    profiles: dict[str, dict[str, Any]]
    adapters: dict[str, dict[str, Any]]


def repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=False
    )
    if result.returncode:
        raise EvoError("current directory is not inside a Git worktree")
    return Path(result.stdout.strip()).resolve()


def load_yaml(path: Path) -> Any:
    try:
        return load_strict_yaml(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise EvoError(f"{path}: cannot read YAML: {exc}") from exc


def schema_errors(instance: Any, schema_path: Path, label: Path) -> list[str]:
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
    except (OSError, json.JSONDecodeError, SchemaError) as exc:
        return [f"{schema_path}: invalid schema: {exc}"]
    errors = []
    for error in Draft202012Validator(schema).iter_errors(instance):
        location = ".".join(str(part) for part in error.absolute_path)
        errors.append(f"{label}{':' + location if location else ''}: {error.message}")
    return errors


def adapter_errors(data: Any, engine: Path, adapter_id: str) -> list[str]:
    """Keep adapter schema and identity checks consistent across CLI entry points."""
    path = engine / "adapters" / f"{adapter_id}.yaml"
    errors = schema_errors(data, engine / "schemas/adapter.schema.json", path)
    if not errors and data["id"] != adapter_id:
        errors.append(f"{path}: id must equal filename (expected {adapter_id!r}, found {data['id']!r})")
    return errors


def parse_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\n(.*?)\n---\n(.*)\Z", text, re.S)
    if not match:
        raise EvoError(f"{path}: missing YAML frontmatter")
    data = load_strict_yaml(match.group(1))
    if not isinstance(data, dict):
        raise EvoError(f"{path}: frontmatter must be a mapping")
    if not all(isinstance(key, str) for key in data):
        raise EvoError(f"{path}: frontmatter keys must be strings")
    return data, match.group(2)


def parse_command_interface(body: str, path: Path) -> tuple[dict[str, Any], dict[str, str]]:
    blocks = re.findall(r"```yaml ai-evo-interface\n(.*?)\n```", body, re.S)
    if len(blocks) != 1:
        raise EvoError(f"{path}: command must contain exactly one yaml ai-evo-interface block")
    data = load_strict_yaml(blocks[0])
    if isinstance(data, dict) and "executor" in data:
        raise EvoError(f"{path}: commands always use the current AI; executor is only supported on recipe steps")
    if not isinstance(data, dict) or set(data) != {"inputs", "execution-policy"}:
        raise EvoError(f"{path}: interface must contain only inputs and execution-policy")
    policy = data.get("execution-policy")
    if not isinstance(data.get("inputs"), dict) or not isinstance(policy, dict):
        raise EvoError(f"{path}: malformed command interface")
    if (
        set(policy) != {"workspace", "network"}
        or not all(isinstance(value, str) for value in policy.values())
        or policy["workspace"] not in {"read-only", "read-write"}
        or policy["network"] not in {"disabled", "enabled", "auto"}
    ):
        raise EvoError(f"{path}: invalid execution-policy")
    return data["inputs"], policy


def validate_inputs(inputs: Any, label: str) -> list[str]:
    errors = []
    if not isinstance(inputs, dict):
        return [f"{label}: inputs must be a mapping"]
    for name, spec in inputs.items():
        if not re.fullmatch(r"[a-z][a-z0-9_]*", str(name)):
            errors.append(f"{label}: invalid input name {name!r}")
        if not isinstance(spec, dict):
            errors.append(f"{label}.{name}: definition must be a mapping")
            continue
        if set(spec) - {"description", "required", "default"}:
            errors.append(f"{label}.{name}: unsupported keys")
        if not isinstance(spec.get("description"), str) or not spec.get("description"):
            errors.append(f"{label}.{name}: description is required")
        required, default = "required" in spec, "default" in spec
        if required and spec["required"] is not True:
            errors.append(f"{label}.{name}: required must be the boolean true")
        if required == default:
            errors.append(f"{label}.{name}: declare exactly one of required: true or a string default")
        if default and not isinstance(spec["default"], str):
            errors.append(f"{label}.{name}: default must be a string")
    return errors


def parse_variable(value: Any) -> tuple[str, str] | None:
    if not isinstance(value, str):
        return None
    match = INPUT_VAR_RE.fullmatch(value)
    if match:
        return "inputs", match.group(1)
    match = STEP_VAR_RE.fullmatch(value)
    if match:
        return "steps", match.group(1)
    return None


def is_within(path: Path, root: Path) -> bool:
    resolved_path = path.resolve(strict=False)
    resolved_root = root.resolve(strict=False)
    return resolved_path == resolved_root or resolved_root in resolved_path.parents


def target_path_errors(repo: Path, skills: Path, targets: list[dict[str, Any]], config_path: Path) -> list[str]:
    """Check publication destinations before init, planning or synchronization writes."""
    errors: list[str] = []
    target_ids = [target["id"] for target in targets]
    configured_target_paths = [repo / target["path"] for target in targets]
    target_paths: list[Path] = []
    for path in configured_target_paths:
        try:
            # Check the existing prefix first: a cyclic alias is not a usable
            # directory, even on Python versions with permissive resolve().
            require_directory_path(path)
            target_paths.append(path.resolve(strict=False))
        except (EvoError, OSError, RuntimeError) as exc:
            errors.append(f"{config_path}: invalid publication target {path}: {exc}")
    if errors:
        return errors
    if len(target_ids) != len(set(target_ids)):
        errors.append(f"{config_path}: target ids must be unique")
    if len(target_paths) != len(set(target_paths)):
        errors.append(f"{config_path}: target paths must be unique after resolving filesystem aliases")
    # Keep lexical containment checks too: a previously published skill symlink
    # can resolve an otherwise nested target into a different directory tree.
    for index, path in enumerate(configured_target_paths):
        if repo not in target_paths[index].parents:
            errors.append(f"{path}: target directory resolves outside the Git worktree")
        for source in (skills / "catalog", skills / "custom"):
            pairs = ((path, source), (target_paths[index], source.resolve(strict=False)))
            if any(target == origin or target in origin.parents or origin in target.parents
                   for target, origin in pairs):
                errors.append(f"{config_path}: target path must not overlap skill sources: {path} and {source}")
        for other_index in range(index + 1, len(configured_target_paths)):
            other = configured_target_paths[other_index]
            resolved, resolved_other = target_paths[index], target_paths[other_index]
            if (path in other.parents or other in path.parents
                    or resolved in resolved_other.parents or resolved_other in resolved.parents):
                errors.append(f"{config_path}: target paths must not overlap: {path} and {other}")

    return errors


def load_context(require_config: bool = True, *, for_creation: bool = False) -> tuple[Context | None, list[str]]:
    errors: list[str] = []
    repo = repo_root()
    engine = repo / ".ai-evo"
    project = repo / ".ai-evo-prj"
    skills = project / "skills"
    config_path = repo / ".ai-evo-skills.yaml"
    if not config_path.exists():
        if require_config:
            errors.append(f"{config_path}: missing project configuration")
        return None, errors
    try:
        config = load_yaml(config_path)
    except EvoError as exc:
        return None, [str(exc)]
    errors += schema_errors(config, engine / "schemas/project-config.schema.json", config_path)
    if errors:
        return None, errors
    namespace = config["namespace"]
    for target in config["targets"]:
        configured_path = Path(target["path"])
        if configured_path.is_absolute() or ".." in configured_path.parts or configured_path == Path("."):
            errors.append(f"{config_path}: target path {target['path']!r} must be a project-relative child path")
    if errors:
        return None, errors
    registry: dict[str, Skill] = {}
    custom_commands = skills / "custom/commands"
    if not is_within(custom_commands, project):
        errors.append(f"{custom_commands}: custom commands directory resolves outside the project area")
    elif custom_commands.exists():
        if not custom_commands.is_dir():
            errors.append(f"{custom_commands}: expected a directory")
        elif any(custom_commands.iterdir()):
            errors.append(f"{custom_commands}: personal commands are not allowed; add commands to the shared catalog")
    roots = [skills / "catalog/commands", skills / "catalog/recipes", skills / "custom/recipes"]
    for root in roots:
        if not is_within(root, project):
            errors.append(f"{root}: canonical skill directory resolves outside the project area")
            continue
        if os.path.lexists(root) and root.is_symlink():
            errors.append(f"{root}: canonical skill directories must be real project directories")
            continue
        if not root.exists():
            continue
        if not root.is_dir():
            errors.append(f"{root}: canonical skill directories must be real project directories")
            continue
        for item in sorted(root.iterdir()):
            if item.is_symlink():
                errors.append(f"{item}: skill directories may not be symbolic links")
            elif not item.is_dir():
                errors.append(f"{item}: skill collections may contain only skill directories")
            elif (item / "SKILL.md").is_symlink():
                errors.append(f"{item / 'SKILL.md'}: skill files may not be symbolic links")
            elif not (item / "SKILL.md").exists():
                errors.append(f"{item}: missing SKILL.md")
        for path in sorted(root.glob("*/SKILL.md")):
            if path.parent.is_symlink() or path.is_symlink():
                continue
            if for_creation:
                # Reserve names and validate storage without requiring draft content
                # to be executable. Publishing and planning still validate everything.
                name = path.parent.name
                if not NAME_RE.fullmatch(name) or len(name) > 64 or not name.startswith(namespace + "-"):
                    errors.append(f"{path.parent}: invalid namespaced skill name")
                if root.name == "recipes" and (diagnostic := recipe_name_error(name, namespace)):
                    errors.append(f"{path.parent}: {diagnostic}")
                if name in registry:
                    errors.append(f"{path}: duplicate skill name {name}")
                registry[name] = Skill(name, "command" if root.name == "commands" else "recipe", path, {})
                continue
            try:
                front, body = parse_frontmatter(path)
            except (EvoError, OSError, yaml.YAMLError) as exc:
                errors.append(str(exc))
                continue
            name = front.get("name")
            metadata = front.get("metadata") if isinstance(front.get("metadata"), dict) else {}
            kind = metadata.get("ai-evo-kind")
            expected_kind = "command" if root.name == "commands" else "recipe"
            if expected_kind == "recipe":
                candidates = dict.fromkeys((path.parent.name, name)) if isinstance(name, str) else (path.parent.name,)
                for candidate in candidates:
                    if diagnostic := recipe_name_error(candidate, namespace):
                        errors.append(f"{path}: {diagnostic}")
            if name != path.parent.name:
                errors.append(f"{path}: frontmatter name must equal directory name")
            if not isinstance(name, str) or not NAME_RE.fullmatch(name) or len(name) > 64:
                errors.append(f"{path}: invalid skill name")
                continue
            if not name.startswith(namespace + "-"):
                errors.append(f"{path}: skill name must start with {namespace}-")
            if name in registry:
                errors.append(f"{path}: duplicate skill name {name}")
            allowed_frontmatter = {
                "name",
                "description",
                "license",
                "compatibility",
                "metadata",
                "allowed-tools",
            }
            unknown_frontmatter = set(front) - allowed_frontmatter
            if unknown_frontmatter:
                errors.append(f"{path}: unsupported frontmatter fields: {', '.join(sorted(unknown_frontmatter))}")
            if not isinstance(front.get("metadata"), dict) or not all(
                isinstance(key, str) and isinstance(value, str) for key, value in metadata.items()
            ):
                errors.append(f"{path}: metadata must map strings to strings")
            if kind != expected_kind:
                errors.append(f"{path}: ai-evo-kind must be {expected_kind}")
            if metadata.get("ai-evo-version") != PROTOCOL_VERSION:
                errors.append(f"{path}: ai-evo-version must be {PROTOCOL_VERSION!r}")
            if not isinstance(front.get("description"), str) or not front["description"].strip():
                errors.append(f"{path}: description is required")
            elif len(front["description"]) > 1024:
                errors.append(f"{path}: description exceeds 1024 characters")
            if "license" in front and (
                not isinstance(front["license"], str) or not front["license"].strip()
            ):
                errors.append(f"{path}: license must be a non-empty string")
            if "compatibility" in front and (
                not isinstance(front["compatibility"], str)
                or not front["compatibility"].strip()
                or len(front["compatibility"]) > 500
            ):
                errors.append(f"{path}: compatibility must be a non-empty string of at most 500 characters")
            if "allowed-tools" in front and not isinstance(front["allowed-tools"], str):
                errors.append(f"{path}: allowed-tools must be a string")
            found = re.findall(r"^## (.+)$", body, re.M)
            if found != SECTIONS:
                errors.append(f"{path}: required sections must appear once in the documented order")
            if len(re.findall(r"^# (.+)$", body, re.M)) != 1 or not body.lstrip("\n").startswith("# "):
                errors.append(f"{path}: exactly one non-empty H1 title must precede the required sections")
            for index, section in enumerate(SECTIONS):
                end = SECTIONS[index + 1] if index + 1 < len(SECTIONS) else None
                pattern = fr"^## {re.escape(section)}\n(.*?)(?=^## {re.escape(end)}\n|\Z)" if end else fr"^## {re.escape(section)}\n(.*)\Z"
                match = re.search(pattern, body, re.M | re.S)
                if match and not match.group(1).strip():
                    errors.append(f"{path}: section {section} must not be empty")
            if "TODO" in body or any(isinstance(value, str) and "TODO" in value for value in front.values()):
                errors.append(f"{path}: unresolved TODO placeholder")
            recipe = None
            execution_policy = None
            inputs: dict[str, Any] = {}
            if expected_kind == "command":
                extra = [item.name for item in path.parent.iterdir() if item.name != "SKILL.md"]
                if extra:
                    errors.append(f"{path.parent}: command directory may contain only SKILL.md: {', '.join(extra)}")
                try:
                    inputs, execution_policy = parse_command_interface(body, path)
                except (EvoError, yaml.YAMLError) as exc:
                    errors.append(str(exc))
                errors += validate_inputs(inputs, f"{path}:inputs")
            else:
                recipe_path = path.parent / "recipe.yaml"
                if not recipe_path.exists():
                    errors.append(f"{recipe_path}: missing")
                elif recipe_path.is_symlink():
                    errors.append(f"{recipe_path}: recipe files may not be symbolic links")
                else:
                    try:
                        recipe = load_yaml(recipe_path)
                        if isinstance(recipe, dict) and isinstance(recipe.get("name"), str):
                            if diagnostic := recipe_name_error(recipe["name"], namespace):
                                errors.append(f"{recipe_path}: {diagnostic}")
                        if isinstance(recipe, dict) and "executor" in recipe:
                            errors.append(f"{recipe_path}: recipes always use the current AI; executor is only supported on recipe steps")
                        recipe_validation = schema_errors(recipe, engine / "schemas/recipe.schema.json", recipe_path)
                        errors += recipe_validation
                        if not recipe_validation and isinstance(recipe, dict):
                            inputs = recipe.get("inputs", {})
                            if recipe.get("name") != name:
                                errors.append(f"{recipe_path}: name must equal SKILL name")
                        if recipe_validation:
                            recipe = None
                    except EvoError as exc:
                        errors.append(str(exc))
                extra = [item.name for item in path.parent.iterdir() if item.name not in {"SKILL.md", "recipe.yaml"}]
                if extra:
                    errors.append(f"{path.parent}: recipe directory may contain only SKILL.md and recipe.yaml: {', '.join(extra)}")
            registry[name] = Skill(name, expected_kind, path, inputs, execution_policy, recipe)

    profiles: dict[str, dict[str, Any]] = {}
    profiles_root = skills / "config/effort-profiles"
    if not is_within(profiles_root, project) or (
        os.path.lexists(profiles_root) and (profiles_root.is_symlink() or not profiles_root.is_dir())
    ):
        errors.append(f"{profiles_root}: effort profiles must use a real project directory")
        profile_paths: list[Path] = []
    else:
        profile_paths = sorted(profiles_root.glob("*.yaml"))
    for path in profile_paths:
        if for_creation:
            continue
        try:
            data = load_yaml(path)
            validation = schema_errors(data, engine / "schemas/effort-profile.schema.json", path)
            errors += validation
            if isinstance(data, dict) and "TODO" in str(data.get("description", "")):
                errors.append(f"{path}: unresolved TODO placeholder")
            if isinstance(data, dict) and not validation:
                name = data.get("name")
                if name != path.stem:
                    errors.append(f"{path}: name must equal filename")
                if not isinstance(name, str) or not name.startswith(namespace + "-"):
                    errors.append(f"{path}: profile name must start with {namespace}-")
                elif name in profiles:
                    errors.append(f"{path}: duplicate profile {name}")
                else:
                    profiles[name] = data
        except EvoError as exc:
            errors.append(str(exc))
    if not for_creation and namespace + "-default" not in profiles:
        errors.append(f"missing default effort profile {namespace}-default")

    adapters: dict[str, dict[str, Any]] = {}
    configured_adapters = sorted({target["adapter"] for target in config["targets"]})
    for adapter_id in configured_adapters:
        path = engine / "adapters" / f"{adapter_id}.yaml"
        if not path.is_file():
            errors.append(f"{config_path}: unknown adapter {adapter_id}")
            continue
        try:
            data = load_yaml(path)
            validation = adapter_errors(data, engine, adapter_id)
            errors += validation
            if isinstance(data, dict) and isinstance(data.get("id"), str) and not validation:
                adapter_paths = [data["project-skill-path"], data["project-entrypoint"]["path"], data["project-entrypoint"]["template"]]
                if any(Path(value).is_absolute() or ".." in Path(value).parts or Path(value) == Path(".") for value in adapter_paths):
                    errors.append(f"{path}: adapter paths must be relative child paths and may not contain ..")
                    continue
                adapters[data["id"]] = data
        except EvoError as exc:
            errors.append(str(exc))
    if not (project / "entrypoint.md").is_file():
        errors.append(f"{project / 'entrypoint.md'}: missing project entrypoint")
    for target in config["targets"]:
        if not target["enabled"]:
            continue
        adapter = adapters.get(target["adapter"])
        if not adapter:
            errors.append(f"{config_path}: unknown adapter {target['adapter']}")
            continue
        entry = repo / adapter["project-entrypoint"]["path"]
        if not entry.is_file():
            errors.append(f"{entry}: required by enabled adapter {adapter['id']}")
        elif adapter["project-entrypoint"]["must-reference"] not in entry.read_text(encoding="utf-8"):
            errors.append(f"{entry}: must reference {adapter['project-entrypoint']['must-reference']}")

    errors += target_path_errors(repo, skills, config["targets"], config_path)

    known_adapters = {path.stem for path in (engine / "adapters").glob("*.yaml")}
    for skill in registry.values():
        if skill.recipe is not None:
            for step in skill.recipe["steps"]:
                executor = step.get("executor", "current")
                if executor != "current" and executor not in known_adapters:
                    errors.append(f"{skill.path.parent / 'recipe.yaml'}:steps.{step['id']}: unknown executor adapter {executor}")

    directives = project / "directives"
    for path in directives.iterdir() if directives.exists() else []:
        if path.name == "README.md":
            continue
        if not path.is_file() or not re.fullmatch(fr"{namespace}-[a-z0-9]+(?:-[a-z0-9]+)*\.md", path.name):
            errors.append(f"{path}: project directive must use {namespace}-<kebab-case>.md")

    context = Context(repo, engine, project, skills, config, registry, profiles, adapters)
    errors += validate_recipes(context)
    errors += validate_recipe_executors(context)
    return context, errors


def validate_recipes(context: Context) -> list[str]:
    errors: list[str] = []
    graph: dict[str, list[str]] = {}
    for skill in context.registry.values():
        if skill.kind != "recipe" or not isinstance(skill.recipe, dict):
            continue
        recipe, seen, prior = skill.recipe, set(), set()
        graph[skill.name] = []
        for step in recipe.get("steps", []):
            if not isinstance(step, dict):
                continue
            sid, used = step.get("id"), step.get("uses")
            if sid in seen:
                errors.append(f"{skill.path.parent / 'recipe.yaml'}: duplicate step id {sid}")
            seen.add(sid)
            child = context.registry.get(used)
            if not child:
                suggestion = recipe_name_error(used, context.config["namespace"])
                candidate = context.config["namespace"] + "-recipe-" + used.partition('-')[2].removeprefix('recipe-')
                renamed = context.registry.get(candidate)
                hint = f"; {suggestion}" if suggestion and renamed and renamed.kind == "recipe" else ""
                errors.append(f"{skill.path.parent / 'recipe.yaml'}: unknown skill {used}{hint}")
                continue
            if child.kind == "recipe":
                graph[skill.name].append(child.name)
            supplied = step.get("with", {}) or {}
            unknown = set(supplied) - set(child.inputs)
            for name in sorted(unknown):
                errors.append(f"{skill.name}.{sid}: unknown child input {name}")
            for name, spec in child.inputs.items():
                if not isinstance(spec, dict):
                    # Structural validation already reports this definition;
                    # keep collecting recipe errors without dereferencing it.
                    continue
                if spec.get("required") is True and name not in supplied:
                    errors.append(f"{skill.name}.{sid}: required child input {name} is not mapped")
            references = dict(supplied)
            if "when" in step:
                references["when.value"] = step["when"]["value"]
            for key, value in references.items():
                variable = parse_variable(value)
                if isinstance(value, str) and "${{" in value and not variable:
                    errors.append(f"{skill.name}.{sid}.{key}: invalid variable expression; "
                                  "references must occupy the entire value (partial interpolation is unsupported)")
                elif variable and variable[0] == "inputs" and variable[1] not in skill.inputs:
                    errors.append(f"{skill.name}.{sid}.{key}: unknown recipe input {variable[1]}")
                elif variable and variable[0] == "steps" and variable[1] not in prior:
                    errors.append(f"{skill.name}.{sid}.{key}: step output must reference a previous step")
            prior.add(sid)
        output = recipe.get("outputs", {}).get("result", {}).get("value", "")
        variable = parse_variable(output)
        if not variable or variable[0] != "steps" or variable[1] not in prior:
            errors.append(f"{skill.name}: outputs.result.value must reference an existing step output")

    state: dict[str, int] = {}
    stack: list[str] = []
    def visit(node: str) -> None:
        state[node], stack[:] = 1, stack + [node]
        for child in graph.get(node, []):
            if state.get(child) == 1:
                start = stack.index(child)
                errors.append("recipe cycle: " + " -> ".join(stack[start:] + [child]))
            elif state.get(child, 0) == 0:
                visit(child)
        stack.pop()
        state[node] = 2
    for node in graph:
        if state.get(node, 0) == 0:
            visit(node)
    return errors


def validate_recipe_executors(context: Context) -> list[str]:
    """Every recipe is published to all enabled targets; check each call's override."""
    errors: list[str] = []
    enabled = {target["adapter"] for target in context.config["targets"] if target["enabled"]}
    if not enabled:
        return errors
    for recipe in context.registry.values():
        if recipe.kind != "recipe" or not isinstance(recipe.recipe, dict):
            continue
        for step in recipe.recipe["steps"]:
            child = context.registry.get(step.get("uses"))
            if child is None:
                continue
            executor = step.get("executor", "current")
            if executor != "current" and executor not in enabled:
                kind = "command" if child.kind == "command" else "nested recipe"
                errors.append(f"{recipe.name}:steps.{step['id']}: {kind} {child.name} requires disabled adapter {executor}")
    return errors


def validated_context(*, for_creation: bool = False) -> Context:
    context, errors = load_context(for_creation=for_creation)
    if errors:
        raise EvoError("validation failed:\n" + "\n".join(f"- {error}" for error in errors))
    assert context is not None
    return context


def resolve_inputs(definitions: dict[str, Any], values: list[str]) -> dict[str, str]:
    supplied: dict[str, str] = {}
    for token in values:
        if "=" not in token:
            raise EvoError(f"invalid input {token!r}; expected key=value")
        key, value = token.split("=", 1)
        if key in supplied:
            raise EvoError(f"duplicate input {key}")
        if key not in definitions:
            raise EvoError(f"unknown input {key}")
        supplied[key] = value
    for key, spec in definitions.items():
        if key not in supplied:
            if "default" in spec:
                supplied[key] = spec["default"]
            else:
                raise EvoError(f"missing required input {key}")
    return supplied


def profile_payload(context: Context, name: str | None, adapter_id: str) -> dict[str, Any]:
    selected = name or context.config["namespace"] + "-default"
    profile = context.profiles.get(selected)
    if not profile:
        raise EvoError(f"unknown effort profile {selected}")
    adapter = context.adapters.get(adapter_id)
    if not adapter:
        raise EvoError(f"unknown adapter {adapter_id}")
    if adapter_id not in {target["adapter"] for target in context.config["targets"] if target["enabled"]}:
        raise EvoError(f"adapter {adapter_id} is not enabled for this project")
    instructions = [
        f"Use {profile['reasoning']['level']} reasoning effort.",
        f"Subagents: {profile['resources']['subagents']}; network: {profile['resources']['network']}.",
        f"Concurrent work on the same worktree: {str(profile['execution']['concurrent-on-same-worktree']).lower()}.",
        f"Session reuse: {profile['execution']['reuse-session']}.",
        f"Output delivery: {profile['output']['delivery']}; verbose logs: {profile['output']['verbose-logs']}.",
        f"Tests: {profile['tests']['strategy']}; repeat passed tests: {str(profile['tests']['repeat-passed']).lower()}.",
        f"Repeat readable content: {str(profile['context']['repeat-readable-content']).lower()}; repository exploration: {profile['context']['repository-exploration']}.",
    ]
    delegated: list[str] = []
    translation = adapter["profile-translation"]["delegated-cli"]
    if translation:
        delegated += [translation["reasoning-option"], profile["reasoning"]["level"]]
        denied = []
        for resource in ("subagents", "network"):
            if profile["resources"][resource] == "disabled":
                denied.extend(translation["resource-tools"][resource])
        if denied:
            delegated += [translation["disallowed-tools-option"], ",".join(denied)]
    if adapter_id == "claude":
        try:
            delegated = normalize_claude_arguments(delegated)
        except ClaudePolicyError as exc:
            raise EvoError(str(exc)) from exc
    return {
        "version": PROTOCOL_VERSION,
        "profile": selected,
        "adapter": adapter_id,
        "application": "native-cli-and-instructions" if delegated else "instructions",
        "delegated_cli_arguments": delegated,
        "instructions": instructions,
        "reporting": profile["report"]["profile-application"],
    }


def command_application(
    context: Context, skill: Skill, profile_name: str | None, current_adapter: str,
    *, executor: str = "current",
) -> dict[str, Any]:
    adapter_id = current_adapter if executor == "current" else executor
    payload = profile_payload(context, profile_name, adapter_id)
    adapter = context.adapters[adapter_id]
    arguments = list(payload["delegated_cli_arguments"])
    reuse = context.profiles[payload["profile"]]["execution"]["reuse-session"]
    arguments.extend(adapter.get("session-translation", {}).get(reuse, []))
    policy_instructions: list[str] = []
    policy = skill.execution_policy or {}
    for dimension, value in policy.items():
        if (dimension, value) == ("workspace", "read-write"):
            translation = adapter["execution-policy-translation"].get("workspace-read-write")
            if translation:
                arguments.extend(translation["cli-arguments"])
                policy_instructions.extend(translation.get("instructions", []))
            continue
        if (dimension, value) not in {("workspace", "read-only"), ("network", "disabled")}:
            continue
        key = f"{dimension}-{value}"
        translation = adapter["execution-policy-translation"].get(key)
        if not translation or translation.get("enforcement") != "native":
            raise EvoError(f"adapter {adapter_id} cannot enforce {key} for {skill.name}")
        arguments.extend(translation["cli-arguments"])
        policy_instructions.extend(translation.get("instructions", []))
    deny_option = adapter["profile-translation"]["delegated-cli"].get("disallowed-tools-option") if adapter["profile-translation"]["delegated-cli"] else None
    command = adapter["invocation"]["command"]
    if adapter_id == "claude":
        try:
            arguments = normalize_claude_arguments(command[1:], arguments)
        except ClaudePolicyError as exc:
            raise EvoError(str(exc)) from exc
        command = command[:1]
    elif deny_option:
        compact, denied, index = [], [], 0
        while index < len(arguments):
            if arguments[index] == deny_option and index + 1 < len(arguments):
                denied.extend(arguments[index + 1].split(",")); index += 2
            else:
                compact.append(arguments[index]); index += 1
        if denied:
            compact.extend([deny_option, ",".join(dict.fromkeys(denied))])
        arguments = compact
    restrictive_policy = policy.get("workspace") == "read-only" or policy.get("network") == "disabled"
    delegated = executor != "current" or restrictive_policy
    return {
        "executor": adapter_id,
        "mode": "delegated" if delegated else "current",
        "command": command,
        "prompt_delivery": adapter["invocation"].get("prompt-delivery", "argument-after-options"),
        "working_directory": str(context.repo),
        "cli_arguments": arguments,
        "execution_policy": policy,
        "session": {
            "reuse": reuse,
            "resume_permitted": reuse != "never",
            "resume_supported": bool(adapter["invocation"].get("resume-arguments")),
            "resume_allowed": reuse != "never" and bool(adapter["invocation"].get("resume-arguments")),
            "corrections_only": reuse == "correction-only",
            "resume_arguments": adapter["invocation"].get("resume-arguments"),
        },
        "policy_instructions": list(dict.fromkeys(policy_instructions)),
        "profile": payload,
    }


def cmd_validate(_: argparse.Namespace) -> None:
    context, errors = load_context()
    if errors:
        raise EvoError("validation failed:\n" + "\n".join(f"- {error}" for error in errors))
    print(f"Valid: {len(context.registry)} skills, {len(context.profiles)} effort profiles, {len(context.config['targets'])} targets.")


def managed_link(path: Path, source_roots: list[Path]) -> bool:
    if not path.is_symlink():
        return False
    try:
        target = path.parent / os.readlink(path)
        try:
            # Strict resolution detects loops even on Python versions where
            # strict=False returns an unresolved path instead of raising.
            target = target.resolve(strict=True)
        except FileNotFoundError:
            # Deleted catalog entries still leave managed links to remove.
            target = target.resolve(strict=False)
    except (OSError, RuntimeError):
        # Ownership cannot be established: preserve the link as unmanaged.
        return False
    return any(target == root or root in target.parents for root in source_roots)


def cmd_sync(args: argparse.Namespace) -> None:
    context = validated_context()
    source_roots = [(context.skills / "catalog").resolve(), (context.skills / "custom").resolve()]
    actions: list[tuple[str, Path, Path | None]] = []
    physical_ignores: list[str] = []
    for target in context.config["targets"]:
        desired = {
            name: skill
            for name, skill in context.registry.items()
            if target["enabled"]
        }
        directory = context.repo / target["path"]
        resolved_directory = directory.resolve(strict=False)
        # Every configured target can change after init, with or without aliases.
        # Ignore only generated entries and escape Git's pattern metacharacters.
        for name in desired:
            relative = (resolved_directory / name).relative_to(context.repo).as_posix()
            escaped = ''.join('\\' + char if char in '\\*?[] ' else char for char in relative)
            physical_ignores.append('/' + escaped)
        for existing in directory.iterdir() if directory.exists() else []:
            if managed_link(existing, source_roots) and existing.name not in desired:
                actions.append(("remove", existing, None))
        for name, skill in desired.items():
            link = directory / name
            if link.lexists() if hasattr(link, "lexists") else os.path.lexists(link):
                if link.is_symlink() and managed_link(link, source_roots) and link.resolve(strict=False) == skill.path.parent.resolve():
                    continue
                if link.is_symlink() and managed_link(link, source_roots):
                    actions.append(("remove", link, None))
                else:
                    raise EvoError(f"{link}: collision with unmanaged file, directory or symlink")
            actions.append(("link", link, skill.path.parent))
    if physical_ignores and not args.dry_run:
        append_ignore(context.repo / '.gitignore', physical_ignores)
    for operation, path, target in actions:
        if args.dry_run:
            print(f"would {operation}: {path}" + (f" -> {target}" if target else ""))
            continue
        if operation == "remove":
            path.unlink(missing_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            # Relative symlinks are interpreted from the physical parent directory.
            relative = os.path.relpath(target, path.parent.resolve())
            path.symlink_to(relative, target_is_directory=True)
            print(f"linked: {path} -> {relative}")
    if not actions:
        print("Already synchronized.")


def render(template: Path, replacements: dict[str, str]) -> str:
    text = template.read_text(encoding="utf-8")
    for key, value in replacements.items():
        text = text.replace(f"<{key}>", value)
    return text


def append_ignore(path: Path, patterns: list[str]) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    missing = [pattern for pattern in patterns if pattern not in existing.splitlines()]
    if missing:
        suffix = "\n" if existing and not existing.endswith("\n\n") else ""
        path.write_text(existing + suffix + "# AI Evo Skills\n" + "\n".join(missing) + "\n", encoding="utf-8")


def require_directory_path(path: Path) -> None:
    """Reject a path whose existing prefix cannot be used as a directory."""
    candidate = path
    while not os.path.lexists(candidate):
        candidate = candidate.parent
    if not candidate.is_dir():
        raise EvoError(f"{candidate}: expected a directory")


def ensure_short_name(name: str, namespace: str) -> None:
    if name.startswith(namespace + "-"):
        raise EvoError(f"pass the unprefixed name; namespace {namespace}- is added automatically")
    if not SHORT_RE.fullmatch(name):
        raise EvoError("name must use lowercase ASCII words separated by hyphens")


def cmd_create(args: argparse.Namespace) -> None:
    context = validated_context(for_creation=True)
    namespace, short = context.config["namespace"], args.name
    marker = {"command": "cmd", "recipe": "recipe"}.get(args.create_kind)
    if marker:
        if short.startswith(namespace + "-"):
            suggestion = short[len(namespace) + 1:]
            while suggestion.startswith(marker + "-"):
                suggestion = suggestion[len(marker) + 1:]
            suggestion = suggestion if suggestion and suggestion != marker else "<name>"
            raise EvoError(f"pass the unprefixed {args.create_kind} name {suggestion!r}; {namespace}-{marker}- is added automatically")
        if short == marker or short.startswith(marker + "-"):
            suggestion = short
            while suggestion.startswith(marker + "-"):
                suggestion = suggestion[len(marker) + 1:]
            suggestion = suggestion if suggestion and suggestion != marker else "<name>"
            raise EvoError(f"pass the unprefixed {args.create_kind} name {suggestion!r}; {namespace}-{marker}- is added automatically")
        foreign = re.fullmatch(fr"([a-z]{{3,6}})-{marker}-(.+)", short)
        if foreign:
            raise EvoError(f"{args.create_kind} namespace {foreign[1]!r} does not match project namespace {namespace!r}; "
                           f"pass the unprefixed name {foreign[2]!r}")
    ensure_short_name(short, namespace)
    name = f"{namespace}-{marker}-{short}" if marker else f"{namespace}-{short}"
    if len(name) > 64:
        raise EvoError("namespaced artifact name must not exceed 64 characters")
    if args.create_kind in {"command", "recipe"} and name in context.registry:
        existing = context.registry[name]
        raise EvoError(f"skill name {name} is already used by {existing.path.parent}")
    replacements = {"namespace": namespace, "skill-name": short, "profile-name": short}
    if args.create_kind == "command":
        destination = context.skills / "catalog/commands" / name
        files = [(context.engine / "templates/skills/command.SKILL.tpl.md", destination / "SKILL.md")]
    elif args.create_kind == "recipe":
        base = "catalog/recipes" if args.catalog else "custom/recipes"
        destination = context.skills / base / name
        files = [
            (context.engine / "templates/skills/recipe.SKILL.tpl.md", destination / "SKILL.md"),
            (context.engine / "templates/skills/recipe.tpl.yaml", destination / "recipe.yaml"),
        ]
    else:
        destination = context.skills / "config/effort-profiles"
        files = [(context.engine / "templates/skills/effort-profile.tpl.yaml", destination / f"{name}.yaml")]
    collisions = [str(dst) for _, dst in files if os.path.lexists(dst)]
    if collisions:
        raise EvoError("refusing to overwrite: " + ", ".join(collisions))
    rendered = [(destination_file, render(source, replacements)) for source, destination_file in files]
    for destination_file, _ in rendered:
        require_directory_path(destination_file.parent)
        if not is_within(destination_file.parent, context.project):
            raise EvoError(f"{destination_file.parent}: destination resolves outside the project area")

    created_files: list[Path] = []
    created_directories: list[Path] = []
    try:
        for destination_file, content in rendered:
            missing: list[Path] = []
            candidate = destination_file.parent
            while not os.path.lexists(candidate):
                missing.append(candidate)
                candidate = candidate.parent
            destination_file.parent.mkdir(parents=True, exist_ok=True)
            created_directories.extend(reversed(missing))
            created_files.append(destination_file)
            destination_file.write_text(content, encoding="utf-8")
    except Exception:
        for path in reversed(created_files):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        for directory in reversed(created_directories):
            try:
                directory.rmdir()
            except OSError:
                pass
        raise
    for destination_file, _ in rendered:
        print(f"created: {destination_file}")
    print("Complete every TODO before running validate or sync.")


def cmd_init(args: argparse.Namespace) -> None:
    repo = repo_root()
    engine = repo / ".ai-evo"
    project = repo / ".ai-evo-prj"
    skills = project / "skills"
    config_path = repo / ".ai-evo-skills.yaml"
    if os.path.lexists(config_path):
        raise EvoError(f"{config_path}: refusing to overwrite existing configuration")
    namespace = args.namespace
    if not namespace:
        if not sys.stdin.isatty():
            raise EvoError("--namespace is required in non-interactive mode")
        namespace = input("Namespace (3-6 lowercase ASCII letters): ").strip()
    if not re.fullmatch(r"[a-z]{3,6}", namespace):
        raise EvoError("namespace must contain 3-6 lowercase ASCII letters")
    if len(args.adapter) != len(set(args.adapter)):
        raise EvoError("each adapter may be enabled only once")
    if not engine.is_dir():
        raise EvoError(f"{engine}: create the engine symlink before init")
    targets = []
    entrypoint_paths: list[str] = []
    entries_to_create: list[tuple[Path, Path]] = []
    for adapter_id in args.adapter:
        path = engine / "adapters" / f"{adapter_id}.yaml"
        if not path.exists():
            raise EvoError(f"unknown adapter {adapter_id}")
        adapter = load_yaml(path)
        validation = adapter_errors(adapter, engine, adapter_id)
        if validation:
            raise EvoError("invalid adapter:\n" + "\n".join(validation))
        for key in ("project-skill-path",):
            candidate = Path(adapter[key])
            if candidate.is_absolute() or ".." in candidate.parts or candidate == Path("."):
                raise EvoError(f"{path}: {key} must be a project-relative child path")
        entry_path = Path(adapter["project-entrypoint"]["path"])
        template_path = Path(adapter["project-entrypoint"]["template"])
        if any(candidate.is_absolute() or ".." in candidate.parts or candidate == Path(".") for candidate in (entry_path, template_path)):
            raise EvoError(f"{path}: entrypoint paths must be relative child paths and may not contain ..")
        targets.append({"id": adapter_id, "adapter": adapter_id, "path": adapter["project-skill-path"], "enabled": True})
        entrypoint_paths.append(entry_path.as_posix())
        entry = repo / adapter["project-entrypoint"]["path"]
        if os.path.lexists(entry):
            if not entry.is_file():
                raise EvoError(f"{entry}: existing adapter entrypoint is not a file")
            if adapter["project-entrypoint"]["must-reference"] not in entry.read_text(encoding="utf-8"):
                raise EvoError(f"{entry}: existing file must reference {adapter['project-entrypoint']['must-reference']}")
        else:
            template = engine / adapter["project-entrypoint"]["template"]
            if not template.is_file():
                raise EvoError(f"{template}: missing adapter entrypoint template")
            entries_to_create.append((entry, template))
    target_errors = target_path_errors(repo, skills, targets, config_path)
    if target_errors:
        raise EvoError("invalid publication targets:\n" + "\n".join(target_errors))
    profile = skills / "config/effort-profiles" / f"{namespace}-default.yaml"
    generated = [
        (project / "entrypoint.md", engine / "templates/project/entrypoint.tpl.md"),
        (project / "component-map.md", engine / "templates/project/component-map.tpl.md"),
        (project / "README.md", engine / "templates/project/README.tpl.md"),
        (project / "directives/README.md", engine / "templates/directives/README.tpl.md"),
    ]
    profile_template = engine / "templates/skills/effort-profile.tpl.yaml"
    missing_templates = [str(template) for _, template in generated if not template.is_file()]
    if not profile_template.is_file():
        missing_templates.append(str(profile_template))
    if missing_templates:
        raise EvoError("missing engine templates: " + ", ".join(missing_templates))

    default_profiles = list((skills / "config/effort-profiles").glob("*-default.yaml"))
    if os.path.lexists(profile):
        profile_data = load_yaml(profile)
        profile_errors = schema_errors(
            profile_data, engine / "schemas/effort-profile.schema.json", profile
        )
        if profile_errors or not isinstance(profile_data, dict) or profile_data.get("name") != profile.stem:
            details = profile_errors or [f"{profile}: name must equal filename"]
            raise EvoError("existing default profile is invalid:\n" + "\n".join(details))
        create_profile = False
    else:
        other_defaults = [path for path in default_profiles if path != profile]
        if other_defaults:
            raise EvoError(
                f"{project}: appears initialized for another namespace: "
                + ", ".join(path.name for path in other_defaults)
            )
        create_profile = True

    project_directories = [
        project,
        skills / "catalog/commands",
        skills / "catalog/recipes",
        skills / "custom/recipes",
        profile.parent,
        *(destination.parent for destination, _ in generated),
    ]
    entry_directories = [entry.parent for entry, _ in entries_to_create]
    required_directories = [*project_directories, *entry_directories]
    for directory in project_directories:
        require_directory_path(directory)
        if directory != project and not is_within(directory, project):
            raise EvoError(f"{directory}: project directory resolves outside the project area")
    for directory in entry_directories:
        require_directory_path(directory)
        if not is_within(directory, repo):
            raise EvoError(f"{directory}: adapter entrypoint directory resolves outside the Git worktree")
    for destination, _ in generated:
        if os.path.lexists(destination) and not destination.is_file():
            raise EvoError(f"{destination}: existing generated path is not a file")
    for ignore in (repo / ".gitignore", project / ".gitignore"):
        if os.path.lexists(ignore) and not ignore.is_file():
            raise EvoError(f"{ignore}: ignore path is not a file")

    rendered_generated = [
        (destination, render(template, {"namespace": namespace}))
        for destination, template in generated
        if not destination.exists()
    ]
    rendered_entries = [
        (entry, template.read_text(encoding="utf-8")) for entry, template in entries_to_create
    ]
    profile_content = render(
        profile_template, {"namespace": namespace, "profile-name": "default"}
    ).replace(
        'description: "TODO: describe the resource and output policy."',
        "description: Default resource-conscious profile for this project.",
    )
    config = {"version": PROTOCOL_VERSION, "namespace": namespace, "targets": targets}
    app_ignores = [".ai-evo", *[target["path"] + "/" for target in targets]]
    if project.is_symlink():
        app_ignores.append(".ai-evo-prj")
    app_ignores.extend(f"!{path}" for path in entrypoint_paths)

    created_files: list[Path] = []
    created_directories: list[Path] = []
    ignore_snapshots = {
        path: path.read_bytes() if path.exists() else None
        for path in (repo / ".gitignore", project / ".gitignore")
    }
    messages: list[str] = []

    def ensure_directory(directory: Path) -> None:
        missing: list[Path] = []
        candidate = directory
        while not os.path.lexists(candidate):
            missing.append(candidate)
            candidate = candidate.parent
        directory.mkdir(parents=True, exist_ok=True)
        created_directories.extend(reversed(missing))

    def write_new(path: Path, content: str) -> None:
        ensure_directory(path.parent)
        created_files.append(path)
        path.write_text(content, encoding="utf-8")
        messages.append(f"created: {path}")

    try:
        for directory in required_directories:
            ensure_directory(directory)
        for destination, content in rendered_generated:
            write_new(destination, content)
        for entry, content in rendered_entries:
            write_new(entry, content)
        write_new(config_path, yaml.safe_dump(config, sort_keys=False))
        if create_profile:
            write_new(profile, profile_content)
        append_ignore(repo / ".gitignore", app_ignores)
        append_ignore(
            project / ".gitignore", ["skills/custom/", f"{namespace}-current-developer.md"]
        )
    except Exception:
        for path, content in ignore_snapshots.items():
            try:
                if content is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_bytes(content)
            except OSError:
                pass
        for path in reversed(created_files):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        for directory in reversed(created_directories):
            try:
                directory.rmdir()
            except OSError:
                pass
        raise
    for message in messages:
        print(message)


def resolve_value(value: str, inputs: dict[str, Any], outputs: dict[str, Any]) -> Any:
    variable = parse_variable(value)
    if not variable:
        return value
    return inputs[variable[1]] if variable[0] == "inputs" else outputs[variable[1]]


def step_output_reference(step_id: str) -> dict[str, str]:
    """Return the documented runtime placeholder for a prior step result."""
    return {"type": STEP_OUTPUT_REFERENCE_TYPE, "step": step_id}


def cmd_profile_resolve(args: argparse.Namespace) -> None:
    context = validated_context()
    print(json.dumps(profile_payload(context, args.profile, args.adapter), indent=2))


def resolved_handoff(skill: Skill, recipe: bool) -> dict[str, Any]:
    return {
        "type": "ai-evo-resolved-command",
        "version": PROTOCOL_VERSION,
        "planning": {"command": "resolved", "recipe": "resolved" if recipe else "not-applicable"},
        "allow_planning": False,
        "skill_content": skill.path.read_text(encoding="utf-8"),
    }


def cmd_command_execute(args: argparse.Namespace) -> None:
    """Consume a trusted local plan without reading or planning the catalog again."""
    try:
        step = json.load(sys.stdin)
    except (ValueError, OSError) as exc:
        raise EvoError(f"invalid execution plan JSON: {exc}") from exc
    validate_plan(step)
    application = step["application"]
    command, options = application["command"], application["cli_arguments"]
    directory, delivery = application["working_directory"], application["prompt_delivery"]
    argv = [*command, *options]
    if args.resume_session:
        session = application.get("session", {})
        if not isinstance(session, dict) or session.get("reuse") not in ("correction-only", "always"):
            raise EvoError("the resolved profile forbids session reuse")
        if session["reuse"] == "correction-only" and not args.correction:
            raise EvoError("this profile permits resume only with --correction after a failed step")
        resume = session.get("resume_arguments")
        if not isinstance(resume, list) or not resume or not all(isinstance(value, str) for value in resume):
            raise EvoError("this adapter does not define native session resume arguments")
        if args.resume_session.startswith("-"):
            raise EvoError("invalid session id")
        argv.extend(value.replace("<session-id>", args.resume_session) for value in resume)
    elif args.correction:
        raise EvoError("--correction requires --resume-session")
    envelope = {
        "type": "ai-evo-execution-handoff",
        "version": PROTOCOL_VERSION,
        "instructions": [
            "Execute this already planned command directly; do not invoke command plan or recipe plan.",
            "The resolved plan supplies authoritative inputs, working directory, policy, profile and CLI arguments.",
            "Skip planning and delegation instructions in skill_content; perform its task and return its result.",
            "Do not remove AI_EVO_EXECUTION_HANDOFF or attempt to bypass the no-replanning guard.",
        ],
        "correction": args.correction,
        "plan": step,
    }
    prompt = json.dumps(envelope, ensure_ascii=False)
    if delivery == "argument-before-options":
        argv = [*command, prompt, *argv[len(command):]]
    elif delivery == "argument-after-options":
        argv.append(prompt)
    status = run_delegated(
        argv, cwd=directory, env={**os.environ, "AI_EVO_EXECUTION_HANDOFF": "resolved"},
        prompt=prompt if delivery == "stdin" else None, timeout=args.timeout,
    )
    raise SystemExit(status)



def cmd_command_plan(args: argparse.Namespace) -> None:
    context = validated_context()
    skill = context.registry.get(args.name)
    if not skill or skill.kind != "command":
        raise EvoError(f"unknown command {args.name}")
    payload = {
        "version": PROTOCOL_VERSION,
        "command": skill.name,
        "skill_path": str(skill.path),
        "with": resolve_inputs(skill.inputs, args.input),
        "application": command_application(context, skill, args.profile, args.adapter),
        "handoff": resolved_handoff(skill, recipe=False),
    }
    print(json.dumps(payload, indent=2))


def cmd_recipe_advance(_: argparse.Namespace) -> None:
    try:
        request = json.load(sys.stdin)
    except (ValueError, OSError) as exc:
        raise EvoError(f"invalid recipe runtime JSON: {exc}") from exc
    transition = advance_recipe(request)
    print(json.dumps(transition, ensure_ascii=False, indent=2))
    if transition["status"] == "failed":
        raise SystemExit(1)


def cmd_recipe_plan(args: argparse.Namespace) -> None:
    context = validated_context()
    if diagnostic := recipe_name_error(args.name, context.config["namespace"]):
        raise EvoError(diagnostic)
    root = context.registry.get(args.name)
    if not root or root.kind != "recipe":
        raise EvoError(f"unknown recipe {args.name}")
    initial = resolve_inputs(root.inputs, args.input)
    plan: list[dict[str, Any]] = []

    def expand(
        skill: Skill, supplied: dict[str, Any], prefix: str,
        inherited: list[dict[str, Any]], coordinator: str, delegated_scope: bool,
    ) -> Any:
        values = {key: supplied.get(key, spec.get("default")) for key, spec in skill.inputs.items()}
        outputs: dict[str, Any] = {}
        assert skill.recipe is not None
        for step in skill.recipe["steps"]:
            child = context.registry[step["uses"]]
            child_values = {key: resolve_value(value, values, outputs) for key, value in (step.get("with") or {}).items()}
            for key, spec in child.inputs.items():
                if key not in child_values and "default" in spec:
                    child_values[key] = spec["default"]
            full_id = f"{prefix}.{step['id']}" if prefix else step["id"]
            guards = list(inherited)
            if "when" in step:
                guards.append({"value": resolve_value(step["when"]["value"], values, outputs),
                               "equals": step["when"]["equals"]})
                if "normalize" in step["when"]:
                    guards[-1]["normalize"] = step["when"]["normalize"]
            if child.kind == "recipe":
                declared = step.get("executor", "current")
                child_coordinator = coordinator if declared == "current" else declared
                outputs[step["id"]] = expand(
                    child, child_values, full_id, guards, child_coordinator,
                    delegated_scope or declared != "current",
                )
            else:
                executor = step.get("executor", "current")
                # A nested recipe's current AI may differ from the root coordinator.
                # Its commands then need delegated execution, even without restrictions.
                if executor == "current" and (delegated_scope or coordinator != args.adapter):
                    executor = coordinator
                plan.append({"id": full_id, "uses": child.name, "skill_path": str(child.path), "with": child_values, "application": command_application(context, child, args.profile, args.adapter, executor=executor), "handoff": resolved_handoff(child, recipe=True)})
                if guards:
                    plan[-1]["when"] = {"all": guards}
                outputs[step["id"]] = step_output_reference(full_id)
        return resolve_value(skill.recipe["outputs"]["result"]["value"], values, outputs)

    result = expand(root, initial, "", [], args.adapter, False)
    payload = {
        "version": PROTOCOL_VERSION,
        "recipe": root.name,
        "profile": profile_payload(context, args.profile, args.adapter),
        "execution": {"mode": "sequential", "failure": "fail-fast", "steps": plan},
        "result": result,
    }
    if any("when" in step for step in plan):
        payload["execution"]["conditions"] = "exact-equals-v1"
    validate_recipe_snapshot(payload)
    print(json.dumps(payload, indent=2))


def positive_timeout(value: str) -> float:
    try:
        timeout = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("timeout must be a positive finite number of seconds") from exc
    if not math.isfinite(timeout) or timeout <= 0:
        raise argparse.ArgumentTypeError("timeout must be a positive finite number of seconds")
    return timeout


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="ai-evo-skills")
    root.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = root.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate"); validate.set_defaults(func=cmd_validate)
    sync = sub.add_parser("sync"); sync.add_argument("--dry-run", action="store_true"); sync.set_defaults(func=cmd_sync)
    init = sub.add_parser("init"); init.add_argument("--namespace"); init.add_argument("--adapter", action="append", required=True); init.set_defaults(func=cmd_init)
    create = sub.add_parser("create"); create_sub = create.add_subparsers(dest="create_kind", required=True)
    for kind in ("command", "effort-profile"):
        item = create_sub.add_parser(kind)
        prefix = "<namespace>-cmd-" if kind == "command" else "<namespace>-"
        item.add_argument("name", help=f"short name only; {prefix} is added automatically")
        item.set_defaults(func=cmd_create)
    recipe = create_sub.add_parser("recipe")
    recipe.add_argument("name", help="short name only; <namespace>-recipe- is added automatically")
    recipe.add_argument("--catalog", action="store_true"); recipe.set_defaults(func=cmd_create)
    profile = sub.add_parser("profile"); profile_sub = profile.add_subparsers(dest="profile_command", required=True)
    resolve = profile_sub.add_parser("resolve"); resolve.add_argument("--adapter", required=True); resolve.add_argument("--ai-effort-profile", dest="profile"); resolve.set_defaults(func=cmd_profile_resolve)
    command_root = sub.add_parser("command"); command_sub = command_root.add_subparsers(dest="command_command", required=True)
    command_plan = command_sub.add_parser("plan"); command_plan.add_argument("name"); command_plan.add_argument("--adapter", required=True); command_plan.add_argument("--ai-effort-profile", dest="profile"); command_plan.add_argument("--input", action="append", default=[]); command_plan.set_defaults(func=cmd_command_plan)
    execute = command_sub.add_parser("execute"); execute.add_argument("--resume-session"); execute.add_argument("--correction", action="store_true"); execute.add_argument("--timeout", type=positive_timeout, default=900.0); execute.set_defaults(func=cmd_command_execute)
    recipe_root = sub.add_parser("recipe"); recipe_sub = recipe_root.add_subparsers(dest="recipe_command", required=True)
    plan = recipe_sub.add_parser("plan"); plan.add_argument("name"); plan.add_argument("--adapter", required=True); plan.add_argument("--ai-effort-profile", dest="profile"); plan.add_argument("--input", action="append", default=[]); plan.set_defaults(func=cmd_recipe_plan)
    advance = recipe_sub.add_parser("advance"); advance.set_defaults(func=cmd_recipe_advance)
    return root


def main() -> None:
    try:
        args = parser().parse_args()
        if os.environ.get("AI_EVO_EXECUTION_HANDOFF") == "resolved" and args.func in (cmd_command_plan, cmd_recipe_plan, cmd_command_execute, cmd_recipe_advance):
            raise EvoError("handoff is already resolved: execute the supplied task without planning or delegating again")
        args.func(args)
    except (EvoError, ExecutionError, ProcessTreeError, OSError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(124 if isinstance(exc, ExecutionTimeout) else 1) from exc


if __name__ == "__main__":
    main()
