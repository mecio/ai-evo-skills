# Changelog

## Unreleased

Maintenance changes since `0.1.0-beta.2`; no new release or tag has been created.
On-disk project protocol remains `1.0`. Regenerate execution snapshots when adopting these changes.

### Fixed

- Read Linux process identities as bytes so non-UTF-8 process names cannot interrupt timeout cleanup.
- Report non-string skill frontmatter keys with file diagnostics instead of a traceback.

- Supervise delegated Linux process trees as a child subreaper, including detached and double-forked
  orphans. Terminate and reap remaining step descendants on timeout, cancellation and normal completion;
  preserve preexisting unrelated children and use pidfds to avoid PID-reuse signalling races.

- Reject adapter resume templates missing `<session-id>` during validation, consistently with the
  execution snapshot schema, instead of producing unusable plans.

- Reject duplicate YAML keys, including nested policies and skill frontmatter, before values can be
  overwritten. Preserve ordinary aliases and explicit overrides of merged defaults.

- Explicitly use Codex `workspace-write` sandbox for `read-write` commands, including network-disabled runs.
- Report profile resume permission separately from native adapter support. Claude resume is reported as
  unavailable through the core; Codex supports it when permitted by the profile.
- Allow multiple unfinished drafts to be created. Keep storage and name checks during creation and full
  validation before publication/planning. Generate syntactically valid YAML and reject profile TODOs.
- Run an installed engine virtualenv directly, without uv cache locks or bytecode writes in read-only
  sandboxes. Keep frozen uv bootstrap when no installed executable is available.
- Apply Codex `--ephemeral` only for `reuse-session: never`. Preserve native sessions for
  `correction-only` and `always`, independently of read-only workspace policy.
- Disable Git conversion filters in the read wrapper, reject symbolic skill files and equivalent
  target paths, preserve diagnostics for malformed YAML, and reject cross-collection skill name collisions.

### Added

- A packaged execution-plan schema requiring the complete policy, profile, handoff and session contract,
  plus cross-field consistency checks before any delegated process starts.
- A 900-second default execution deadline, adjustable with `--timeout`. Timeout exits 124 and kills the
  process group; SIGINT/SIGTERM cancel with 130/143 and terminate descendants, including those ignoring TERM.
- Native policy probes: Codex read-only/read-write filesystem and network checks, plus authenticated Claude
  edit and network-tool permission checks. Namespace-unavailable skips are explicitly reported, not passes.
- Structured resolved handoffs with skill snapshots, explicit planning status and policy/session data.
- `command execute` consumes delegated plans from stdin, supplies the core handoff and blocks accidental
  recursive planning through an inherited execution marker. Runtime output references must be resolved
  before execution. Native output and failure status are preserved.
- `command execute --resume-session <id> --correction` for native Codex correction sessions, retaining
  the original policy arguments. `never` rejects resume; `correction-only` requires a correction;
  `always` also permits ordinary resume.
- Regression tests for real kernel read-only restrictions, bootstrap, session policy, handoffs and native
  Claude → Codex execution/resume. Native authenticated tests are opt-in with `AI_EVO_LIVE_TESTS=1`.

### Operational notes

- Delegated execution now requires Linux kernel 5.3+, accessible procfs and child-subreaper/pidfd support.
  TERM has a two-second grace period, followed by KILL and up to two seconds for reaping.

- Bootstrap and dependency updates require `uv sync --frozen --project .ai-evo` in a writable context.
- Persistent native session storage must be writable outside the read-only worktree.
- The Git wrapper compares unfiltered content and omits submodules in `status`/`diff`.
- Execution JSON is trusted local input. The inherited no-replanning marker prevents accidental recursion;
  it is not a sandbox against deliberate bypass. The coordinator still owns sequencing and fail-fast.

## 0.1.0-beta.2

- Declare prompt delivery explicitly and use stdin for bundled Codex and Claude Code adapters.

## 0.1.0-beta.1

- First public beta of the CLI, schemas, adapters and project-local catalog layout.
