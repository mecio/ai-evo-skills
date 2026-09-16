---
name: acme-cmd-detect-php-context
description: Resolve the current Git worktree to php72 or php83 using the project script before selecting test suites.
metadata:
  ai-evo-kind: command
  ai-evo-version: "1.0"
---

# Detect the configured PHP context

## Purpose

Resolve the current Git worktree to php72 or php83 using the project script before selecting test suites.

## Interface

```yaml ai-evo-interface
execution-policy:
  workspace: read-only
  network: disabled
inputs: {}
```

## Procedure

1. If an `ai-evo-execution-handoff` is supplied, apply its resolved inputs, working directory, policy and
   profile; continue at step 4 without planning again.
2. Otherwise run `.ai-evo/bin/ai-evo-skills command plan acme-cmd-detect-php-context` with the current adapter,
   each received input as `--input key=value`, and any requested `--ai-effort-profile`. Stop on planning failure.
3. For delegated mode, pass the complete resolved plan JSON to `.ai-evo/bin/ai-evo-skills command execute`
   on stdin, return its output and stop. For current mode, apply the resolved handoff and continue.
4. From the application worktree, run
   `python3 .ai-evo-prj/scripts/acme-worktree-context.py --field context`.
   The script resolves the Git root and reads `.ai-evo-prj/skills/config/acme-worktrees.json`.
5. Require exit code zero and stdout equal to `php72` or `php83` with at most a final newline.
   A missing script, unavailable tool, unconfigured root or invalid output is a failed task. Preserve
   diagnostic stderr separately; never replace failure with a guessed token.
6. Return stdout unchanged, without Markdown, explanation or profile commentary.

## Expected output

Exactly `php72` or `php83`, optionally followed by the script's final newline.

## Constraints

- Use Codex for this command with the bundled adapters; restricted Claude cannot run this project script.
- Do not infer context from the branch name, an installed PHP binary or a dependency file.
- Do not modify files, switch worktrees or access the network.

## Success criteria

- The output is the successful script result for the configured canonical Git root.

## Examples

```text
$acme-cmd-detect-php-context
```
