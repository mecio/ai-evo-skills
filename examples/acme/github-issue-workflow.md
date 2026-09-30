# Acme GitHub issue workflow

This is the complete, direct-recipe workflow for a project boilerplate. Copy the named commands and recipes
into `skills/catalog`; replace only the `acme` namespace. A recipe and every step without `executor` run in
the AI context that invoked the recipe. Do not encode an AI or executor in a command or recipe name.

## Commands to create

| Command | Contract |
|---|---|
| `acme-cmd-design-github-issue` | Discuss one question at a time and return an approved issue draft. |
| `acme-cmd-create-github-issue` | Create the approved draft after explicit remote-write authorization. |
| `acme-cmd-refine-github-issue` | Refine an existing issue with the developer and return its approved body. |
| `acme-cmd-analyze-github-issue-code` | Read the issue, applicable project rules, code and tests; return an evidence-backed implementation plan. |
| `acme-cmd-breakdown-github-issue` | Decide whether the work is single, stacked or an epic, and return the approved work-item map. |
| `acme-cmd-prepare-github-issue-stack` | Derive deterministic branch, parent and ordering data from an approved map. |
| `acme-cmd-implement-github-issue` | Implement one approved work item, including the required local checks. |
| `acme-cmd-review` | Inspect an implementation against its resolved base and report findings. |
| `acme-cmd-verify-github-issue-stack` | Verify findings, tests and inter-item dependencies for an item or epic. |
| `acme-cmd-push-git-stacked-stack` | Push a verified stack only after explicit authorization. |
| `acme-cmd-submit-github-stack-prs` | Create or update draft pull requests only after explicit authorization. |
| `acme-cmd-save-worklog-output` | Persist the complete immutable result of a phase. |
| `acme-cmd-report-github-issue-workflow` | Resolve the latest checkpoint, next recipe and already-known inputs. |

Each command is directly invocable. Its `SKILL.md` declares `ai-evo-kind: command` and
`ai-evo-recipe-only: false`; command interfaces never declare an executor.

## Recipes to create

| Phase | Recipe | Required sequence |
|---|---|---|
| 00 | `acme-recipe-00-design-github-issue` | Design, create, save checkpoint. |
| 01 | `acme-recipe-01-refine-github-issue` | Refine, save checkpoint. |
| 02 | `acme-recipe-02-analyze-github-issue-code` | Analyze, save checkpoint. |
| 03 | `acme-recipe-03-breakdown-github-issue` | Break down, prepare stack data, save checkpoint. |
| 04 | `acme-recipe-04-implement-github-issue` | Implement one item, save implementation checkpoint. |
| 05 | `acme-recipe-05-review-github-issue` | Review, verify the report, save checkpoint. |
| 06 | `acme-recipe-06-verify-github-epic-stack` | Verify all approved epic items and dependencies. |
| 07 | `acme-recipe-07-push-github-stack` | Push the verified stack after authorization. |
| 08 | `acme-recipe-08-submit-github-stack` | Submit draft pull requests after authorization. |

Recipes are direct, bounded entrypoints. They do not invoke each other, repeat a completed phase, or carry a
model-specific suffix. Persist the final output of each phase, let the developer inspect it, then invoke the
next recipe explicitly.

## Recipe pattern

The analysis phase shows the required naming and inheritance pattern. Other phases follow the same structure
with their corresponding command and inputs.

```yaml
version: "1.0"
name: acme-recipe-02-analyze-github-issue-code
input-resolver:
  uses: acme-cmd-report-github-issue-workflow
  with:
    issue: "${{ inputs.issue }}"
    requested_recipe: "acme-recipe-02-analyze-github-issue-code"
inputs:
  issue: { required: true, description: "GitHub issue number or URL." }
  developer_instructions: { default: "", description: "Additional approved constraints." }
  worklog_session_name: { required: true, description: "Canonical worklog session path." }
  worklog_session_input: { required: true, description: "Immutable functional-input JSON." }
steps:
  - id: analyze_issue
    uses: acme-cmd-analyze-github-issue-code
    with:
      issue: "${{ inputs.issue }}"
      developer_instructions: "${{ inputs.developer_instructions }}"
  - id: save_result
    uses: acme-cmd-save-worklog-output
    with:
      session_name: "${{ inputs.worklog_session_name }}"
      recipe_name: acme-recipe-02-analyze-github-issue-code
      session_input: "${{ inputs.worklog_session_input }}"
      step_name: analyze_issue
      source_name: acme-cmd-analyze-github-issue-code
      outcome: succeeded
      output: "${{ steps.analyze_issue.output }}"
      expected_output_sha256: "${{ steps.analyze_issue.output_sha256 }}"
      error: "null"
      complete: "true"
outputs:
  result: { value: "${{ steps.save_result.output }}" }
```

The YAML intentionally has no `executor` fields. An exception belongs on a specific step only when a project
needs to delegate that particular operation; it is never part of the artifact name or command interface.

## Typical invocations

```text
$acme-recipe-00-design-github-issue problem_description="<initial problem>"
$acme-recipe-02-analyze-github-issue-code issue="1234"
$acme-recipe-04-implement-github-issue issue="1234" base_branch="main"
$acme-recipe-05-review-github-issue issue="1234"
```
