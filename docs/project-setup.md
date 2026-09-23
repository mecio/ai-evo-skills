# Project setup and publication

[Back to the README](../README.md)

## Layout and shared worktrees

A normal installation can use a separate specification repository:

```text
/chosen/path/ai-evo-skills/       reusable engine clone
/project/root/
├── .ai-evo -> /chosen/path/ai-evo-skills
├── .ai-evo-prj -> /path/to/project-specs   optional; may be a real directory
├── .ai-evo-skills.yaml                     project integration configuration
├── AGENTS.md                               Codex entrypoint
├── CLAUDE.md                               Claude Code entrypoint
├── .agents/skills/                         generated Codex links
└── .claude/skills/                         generated Claude links

/path/to/project-specs/
├── README.md
├── entrypoint.md
├── component-map.md
├── directives/
├── templates/
├── scripts/                                optional project-owned helpers
└── skills/
    ├── catalog/
    │   ├── commands/                       directly invocable shared operations
    │   └── recipes/                        shared compositions
    │       ├── _steps/                     atomic services available only to recipes
    │       └── _iterations/                nested recipes not published as native skills
    ├── custom/recipes/                     personal, Git-ignored compositions
    └── config/                            effort profiles and optional helper configuration
        └── effort-profiles/
```

`.ai-evo` separates reusable machinery from application knowledge. `.ai-evo-prj` separates project-specific AI
configuration from the application repository when desired. Both may be shared across Git worktrees, while
`.ai-evo-skills.yaml` and generated native links belong to the worktree in which the CLI runs. The CLI always
finds that worktree with `git rev-parse --show-toplevel`.

Directories immediately below `skills/catalog/recipes` are public recipe entrypoints except for the two
reserved underscore collections. `_steps` contains `ai-evo-kind: step` services, while `_iterations` contains
`ai-evo-kind: recipe` compositions used only through another recipe. Both participate in validation and nested
planning, but neither is published. `recipe plan` accepts public and personal recipe entrypoints as roots and
rejects `_iterations` recipes; steps can only appear in a recipe's `uses` field.

Each skill collection contains only skill directories. Do not put `README.md` files or other loose documents
directly in `skills/catalog/commands`, `skills/catalog/recipes`, `skills/custom/recipes`, `_steps` or
`_iterations`; validation treats every entry as a skill directory. Put catalog-wide documentation outside those
collections, for example under `skills/` or at the project root, and keep per-skill material in that skill's
`references/` directory.

Project scripts are optional, authored separately from `init`, and called by command procedures when allowed
by their execution policies. See [commands that use scripts](command-scripts.md) for placement and contracts.

## Initialization details

Before `init`, `.ai-evo-prj` may be a symbolic link to a dedicated project-specification repository. If it does
not exist, `init` creates a real directory. It derives the project root from Git, creates the command, public
recipe, `_steps` and `_iterations` collections, never installs starter skills and never overwrites existing
adapter entrypoints. In an interactive
terminal it asks for a missing namespace; non-interactive use must pass `--namespace`.

When several worktrees share `.ai-evo-prj`, the first `init` creates the project files and default effort profile;
later worktrees validate and reuse them. `init` rejects a different existing namespace and checks structural
collisions before writing. It also applies the same publication-target checks as `validate` and planning,
including usable directory paths, worktree containment and target/source overlaps, before creating any files.
Each selected adapter must pass schema validation and its `id` must match its filename without `.yaml`;
an identity mismatch stops initialization before any project or ignore files are written.
If an operating-system error occurs during creation, it rolls back files and directories
created by that invocation and restores both affected `.gitignore` files.

The namespace must contain 3-6 lowercase ASCII letters. The initial configuration template is
`.ai-evo/templates/project/ai-evo-skills.tpl.yaml`; `init` generates the equivalent root-level
`.ai-evo-skills.yaml`.

`AGENTS.md` and `CLAUDE.md` should contain only the instruction to read `.ai-evo-prj/entrypoint.md`. Shared
project rules belong in that entrypoint and its directives so every enabled AI receives the same guidance.

After bootstrap, the launcher executes `.ai-evo/.venv/bin/ai-evo-skills` directly with bytecode writes
disabled. It calls `uv run --frozen` only when that executable is absent. Bootstrap the environment in a
writable context (`uv sync --frozen --project .ai-evo`) before invoking planners inside read-only sandboxes.
Updating the engine's dependencies also requires an explicit `uv sync --frozen --project .ai-evo`.

## Project configuration

```yaml
version: "1.0"
namespace: acme
ignore-file: git-exclude
targets:
  - id: codex
    adapter: codex
    path: .agents/skills
    enabled: true
  - id: claude
    adapter: claude
    path: .claude/skills
    enabled: false
```

Commands, public shared recipes and personal recipes always use the invoking AI and are published to every
enabled target. Recipes under `_iterations` and steps under `_steps` are resolved only through recipe plans and
are never published. Recipes cannot declare a top-level executor. Step executors select the AI for individual
calls without limiting publication of the public recipe or child command.
See [executor selection](authoring.md#executor-selection) for nested calls and precedence.

Every target keeps an expressive `id`, its engine `adapter`, a project-relative native skill `path` and an
explicit `enabled` value. Disabled targets remain documented, while `sync` removes their managed links.
Target paths must be distinct and must not contain one another, including after resolving symbolic links.
They must also remain separate from `skills/catalog` and `skills/custom`: a target may not equal, contain
or sit inside either source area. Client directories may use symbolic links within the worktree;
published relative links are calculated from their physical directory. `sync` checks every generated link
with Git before writing an anchored ignore rule, so rules from `.gitignore`, `.git/info/exclude`, and
`core.excludesFile` are all honored. `ignore-file` selects where any uncovered links are recorded:
`git-exclude` (the default) writes to `.git/info/exclude`, `gitignore` writes to the project `.gitignore`,
and `none` writes no rules. Existing ignore rules are preserved.
This handles both ordinary target paths changed after `init` and client aliases; `sync --dry-run` does
not change ignore files. Validation and planning reject overlapping targets, destinations outside the
worktree, and paths whose existing prefix is not a directory (including dangling aliases). Missing
directories with a usable parent are allowed and are created only during synchronization.
Cycles in a destination or its parent aliases are rejected with a diagnostic naming the invalid target,
before initialization or synchronization writes any files.

## Validation and safety boundaries

The validator uses the schemas in `schemas/` offline; YAML instances carry protocol `version: "1.0"` and do not
need remote `$schema` URLs. Schema `$id` values are versioned `urn:ai-evo-skills:` identifiers and never trigger a
network lookup. The validator checks only adapters named by project targets, including disabled targets, and
rejects unsafe absolute or parent-traversing paths. `_steps` and `_iterations` must be real directories rather
than symbolic links. Skill directories, `SKILL.md` files and `recipe.yaml` files may not be symbolic links.
Command, step and recipe directories may additionally contain a real `references/` tree
without symbolic links; other artifact-local entries are rejected. `sync` manages only links whose destinations belong to the
canonical catalog or personal recipe area. A recipe that would be published is invalid when a command or nested
call resolves to a disabled adapter, even if that step's condition would skip it.

Step executors must name an adapter supplied by the engine or `current`. The adapter file is validated when
a project target names it; a published recipe cannot use an adapter absent from the project configuration.

The frontmatter accepts the Agent Skills fields `name`, `description`, `license`, `compatibility`, `metadata` and
`allowed-tools`. AI Evo Skills additionally validates their basic types and uses the string metadata keys
`ai-evo-kind` and `ai-evo-version` for its protocol. Commands and steps also require the boolean metadata key
`ai-evo-recipe-only`, respectively `false` and `true`.

The engine validates structure, produces native execution arguments and launches resolved delegated handoffs.
The executing AI and its CLI remain responsible for following the plan, honoring native restrictions and
reporting failures. Review generated plans
and adapters when upgrading an AI CLI whose flags may have changed.
