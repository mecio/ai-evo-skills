---
name: acme-step-check-review-output
description: Check that a recipe's review output is nonempty UTF-8 and pass it through unchanged; this is not a semantic review or approval.
metadata:
  ai-evo-kind: step
  ai-evo-version: "1.0"
  ai-evo-recipe-only: true
---

# Check review output

## Purpose

Reject missing review text before reporting. Demonstrate a recipe-only service executed by the coordinator.

## Interface

```yaml ai-evo-interface
execution-policy:
  workspace: read-write
  network: auto
inputs:
  review:
    description: Complete output of the preceding review command.
    required: true
```

## Procedure

1. Require a resolved recipe handoff; do not plan or invoke this step directly.
2. Write `review` unchanged as UTF-8 to a temporary file, outside tracked application files.
3. Run `python3 .ai-evo-prj/scripts/acme-check-review-output.py --input <file>` from the application root.
   Use the known path directly. Do not delegate to another AI or search for the script.
4. On nonzero exit, preserve stdout, stderr and exit status and report failure to the coordinator.
5. On success return stdout unchanged. Remove only the temporary input created by this step.

## Expected output

The original nonempty UTF-8 review text, including its whitespace.

## Constraints

- Do not modify application files, Git or remote state. The writable policy permits the temporary input.
- `network: auto` is not permission to use the network; no network operation is required or allowed here.
- Nonempty text does not prove a review is correct, approved, or free of findings.

## Success criteria

- Empty or invalid UTF-8 input fails; accepted bytes are preserved exactly.
- The result is supplied to the report command without repeating the review.

## Examples

```yaml
uses: acme-step-check-review-output
executor: current
with:
  review: "${{ steps.review.output }}"
```
