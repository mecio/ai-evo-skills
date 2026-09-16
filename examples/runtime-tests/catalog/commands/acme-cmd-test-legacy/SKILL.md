---
name: acme-cmd-test-legacy
description: Run the project legacy test wrapper in its configured PHP context and report the observed exit status.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
---

# Run the legacy test suite

## Purpose

Run the project legacy test wrapper in its configured PHP context and report the observed exit status.

## Interface

```yaml ai-evo-interface
execution-policy:
  workspace: read-write
  network: disabled
inputs:
  context:
    description: Token returned by acme-cmd-detect-php-context for this worktree.
    required: true
```

## Procedure

1. If an `ai-evo-execution-handoff` is supplied, apply its resolved inputs, working directory, policy and
   profile; continue at step 4 without planning again.
2. Otherwise run `.ai-evo/bin/ai-evo-skills command plan acme-cmd-test-legacy` with the current adapter,
   each received input as `--input key=value`, and any requested `--ai-effort-profile`. Stop on planning failure.
3. For delegated mode, pass the complete resolved plan JSON to `.ai-evo/bin/ai-evo-skills command execute`
   on stdin, return its output and stop. For current mode, apply the resolved handoff and continue.
4. Trim outer whitespace from the supplied `context` locally and require `php72` or `php83`.
   Run `python3 .ai-evo-prj/scripts/acme-worktree-context.py --field context` and require a successful,
   matching result. A mismatch or failed lookup stops this task before running tests.
5. Run `./scripts/run-legacy-tests` from the application Git root. This project-owned executable must
   already select the correct runtime for this checkout, run only the legacy suite and propagate the
   runner's exit status. If it is absent or unavailable under the resolved policy, fail; do not invent,
   install or substitute a runner.
6. Capture the runner's exit code, stdout and stderr. A nonzero exit is a failed task, including when
   stdout contains an apparent success summary. Report the relevant diagnostics and stop.
7. On success, report the context, exact wrapper invoked, observed exit code and test counts when supplied
   by the runner. Identify skipped tests or coverage limits; never fabricate counts or rerun passed tests.

## Expected output

A concise test report on success. Runner errors or failed tests fail the command and stop the recipe.

## Constraints

- Use Codex for this command with the bundled adapters; restricted Claude cannot run the test wrapper.
- Workspace writes are allowed for test caches and artifacts, not for changing source or tests to get a pass.
- Dependencies and the runtime must already be installed; the wrapper must work with network disabled.
- Do not change worktree, execute another suite or hide nonzero exit codes.

## Success criteria

- The requested suite ran in the configured context and its observed outcome is preserved.

## Examples

```text
$acme-cmd-test-legacy context=php83
```
