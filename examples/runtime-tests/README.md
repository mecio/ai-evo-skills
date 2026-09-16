# Tests selected by a scripted runtime context

This example adapts the Enabu catalog's legacy/Unit test workflow: a script identifies the current
worktree's configured PHP context, the recipe selects applicable suites, and an AI reports their results.
It contains four commands, one recipe and a Python helper. It uses the `acme` namespace and can coexist
with the [Acme review catalog](../acme/README.md).

The helper is runnable with Python 3.11+ and Git. **To execute the test steps, supply your project's actual
test wrappers and worktree mapping first.** This example does not include a PHP application, test suites,
VM setup or test dependencies. `init` does not install it automatically.

## What runs where

| Step | Executor | Responsibility |
|---|---|---|
| `php_context` | Codex | Invoke the helper and return its exact `php72` or `php83` token. |
| `legacy_tests` | Codex | Check the context and execute `./scripts/run-legacy-tests`. |
| `unit_tests` | Codex | Execute `./scripts/run-unit-tests` only when the context is `php83`. |
| `report` | Invoking AI | Summarize the supplied reports, including a Unit skip when applicable. |

Either Codex or Claude can coordinate. Codex must be enabled because the first three steps execute
project scripts with restrictive policies. The bundled Claude adapter permits only the engine's Git
wrapper for Bash under these policies. See [scripts and adapter permissions](../../docs/command-scripts.md#adapter-permissions).

## Install in an application checkout

Initialize the application with namespace `acme` and adapter `codex`; also enable `claude` if it will
coordinate. Follow the [installation guide](../../docs/first-skill.md#install-and-initialize). From the
application Git root, copy into a catalog with none of these new names already present:

```bash
mkdir -p .ai-evo-prj/scripts .ai-evo-prj/skills/config
cp -R .ai-evo/examples/runtime-tests/catalog/commands/. .ai-evo-prj/skills/catalog/commands/
cp -R .ai-evo/examples/runtime-tests/catalog/recipes/. .ai-evo-prj/skills/catalog/recipes/
cp .ai-evo/examples/runtime-tests/scripts/acme-worktree-context.py .ai-evo-prj/scripts/
cp .ai-evo/examples/runtime-tests/config/acme-worktrees.json .ai-evo-prj/skills/config/
```

Copy only when the destinations are new, or review existing files before replacing them. For another
namespace, update command and recipe names, references, script/config filenames and documented paths together.

Edit `.ai-evo-prj/skills/config/acme-worktrees.json` to list the actual **absolute Git roots** returned by
`git rev-parse --show-toplevel` in the relevant checkouts. Keep just one entry if you only have one context.
Paths are canonicalized, so aliases through symlinks refer to the same root; duplicate canonical roots fail.
The context is an explicit project setting, not inferred from a branch name or the installed PHP binary.
Registering a root as `php83` does not install or verify PHP 8.3.

Provide these executable wrappers in the application repository:

| Wrapper | Contract |
|---|---|
| `scripts/run-legacy-tests` | Run the project's legacy suite using the runtime assigned to this worktree. |
| `scripts/run-unit-tests` | Run only the project's PHP 8.3 Unit suite; reject other contexts. |

Both wrappers must run from the current application root, work without network access, print the runner's
real diagnostics and propagate its exit code. Configure dependencies beforehand. They may create test
artifacts but must not repair source or tests. If your tests need a VM, container or networked service,
adapt the wrappers and command policies to that environment before use. Do not replace missing runners
with commands that merely print a passing result.

## Check the deterministic part without an AI

From the application checkout, including from a subdirectory:

```bash
# From the Git root; use the corresponding path when running from a subdirectory.
python3 .ai-evo-prj/scripts/acme-worktree-context.py --field context
python3 .ai-evo-prj/scripts/acme-worktree-context.py
```

The first command prints one token and a newline; the second prints a JSON object containing
`schema_version`, `git_root` and `context`. Unconfigured roots, invalid mappings or Git failures exit 1,
write a diagnostic to stderr and emit no success payload. For an isolated check of the source example,
use `--config /path/to/configured/acme-worktrees.json`; this changes the mapping file, not the detected root.

The script is deterministic for the same worktree root and configuration. An AI still invokes it and
returns its result during a recipe; the coordinator checks the token before recording success.

## Validate and invoke

```bash
./.ai-evo/bin/ai-evo-skills validate
./.ai-evo/bin/ai-evo-skills recipe plan acme-recipe-test-legacy-and-unit --adapter codex
./.ai-evo/bin/ai-evo-skills sync --dry-run
./.ai-evo/bin/ai-evo-skills sync
```

Validation checks the catalog, inputs and references. It does not execute the script, validate its
configuration or establish that the test wrappers work. Check those separately before invoking:

```text
$acme-recipe-test-legacy-and-unit
```

In Claude, use `/acme-recipe-test-legacy-and-unit`. Standalone script-backed commands should be invoked
in Codex with the bundled adapters. Native model execution requires installed, authenticated AI CLIs.

| Outcome | Recipe behavior |
|---|---|
| `php72` and successful legacy suite | Skip Unit; report legacy success and Unit not applicable. |
| `php83` and successful suites | Run both suites in sequence; report both results. |
| Invalid detector output or failed helper | Stop before tests. |
| Missing runner or failed suite | Stop immediately; do not run later suites or the final report. |

A failed suite is not a condition-false skip. To diagnose it, invoke a separate diagnostic command with
the captured failure output after the stopped run; recipe conditions do not implement error handlers.
The report consumes previous results and does not rerun tests.

See the [script guide and Enabu use-case inventory](../../docs/command-scripts.md) for branch manifests,
commit validators and other applications of the same pattern.
