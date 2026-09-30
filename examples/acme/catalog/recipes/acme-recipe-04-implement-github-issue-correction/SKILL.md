---
name: acme-recipe-04-implement-github-issue-correction
description: Apply explicit corrections to a locally committed GitHub implementation before publication.
metadata:
  ai-evo-kind: recipe
  ai-evo-version: "1.0"
---

# Correct a local GitHub issue implementation

## Purpose

Apply developer-requested corrections in an independent phase-04 session when an implementation has been committed
locally but has not yet been published.

## Interface

The formal interface is defined in `recipe.yaml`.

## Procedure

Use this optional sibling recipe only after a successful local implementation checkpoint and before a publication
step. Keep the original session immutable. Its `context` must carry the recorded branch, parent and implementation
report; `correction_instructions` must be explicit and non-empty. Verify the worktree and branch before changing
code, preserve existing commits, apply only the requested corrections, run relevant checks and save the complete
updated implementation report. A project that publishes branches must keep its remote write in a distinct later
step or recipe.

## Expected output

The saved, updated implementation result, including the corrections and their local verification evidence.

## Constraints

- Do not resume or alter the original delegated session merely to apply the correction.
- Do not rewrite existing commits or perform a remote write.
- Do not automatically start review or publication.

## Success criteria

The original checkpoint remains immutable and the correction produces one independently reviewable artifact.

## Examples

```text
$acme-recipe-04-implement-github-issue-correction context="<04 checkpoint>" correction_instructions="Use the real fixture-backed repository."
```
