# Changelog

## 0.1.0-beta.3

On-disk protocol: `1.0` (unchanged). Planner handoffs and adapter session fields are additive.
Regenerate execution plans after upgrading; existing skills do not need to be rewritten.

### Fixed

- Run an installed engine virtualenv directly, without uv cache locks or bytecode writes in read-only
  sandboxes. Keep frozen uv bootstrap when no installed executable is available.
- Apply Codex `--ephemeral` only for `reuse-session: never`. Preserve native sessions for
  `correction-only` and `always`, independently of read-only workspace policy.
- Disable Git conversion filters in the read wrapper, reject symbolic skill files and equivalent
  target paths, preserve diagnostics for malformed YAML, and reject cross-collection skill name collisions.

### Added

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

- Bootstrap and dependency updates require `uv sync --frozen --project .ai-evo` in a writable context.
- Persistent native session storage must be writable outside the read-only worktree.
- The Git wrapper compares unfiltered content and omits submodules in `status`/`diff`.
- Execution JSON is trusted local input. The inherited no-replanning marker prevents accidental recursion;
  it is not a sandbox against deliberate bypass. The coordinator still owns sequencing and fail-fast.

## 0.1.0-beta.2

- Declare prompt delivery explicitly and use stdin for bundled Codex and Claude Code adapters.

## 0.1.0-beta.1

- First public beta of the CLI, schemas, adapters and project-local catalog layout.
