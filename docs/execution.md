# Execution and adapter reference

[Back to the README](../README.md)

## Verified adapter versions

The bundled adapters currently support Codex and Claude Code. Other clients require an adapter and native policy
translations. Their CLI arguments were verified with Codex CLI `0.153.4` and Claude Code `2.1.266`; use those or
compatible newer versions and review adapter changes when vendor flags change. Windows support is outside this beta.

Claude policy composition is also exercised with Claude Code `2.1.268`. The adapter targets the
`2.1.266+` CLI contract, not the older `2.1.68` flag set. It uses `Agent` and the current editing tools
`Edit`, `Write`, `NotebookEdit`; the obsolete `MultiEdit` deny entry has been removed.

## Execution policies and prompt delivery

Commands may declare `output-schema: references/result.schema.json` in their `ai-evo-interface`.
The schema must describe an object, use local JSON-pointer references only, and reside inside the
skill's references directory. It is validated and embedded in the plan, so execution never reloads
a potentially changed schema from the catalog.

The deterministic extractor accepts a JSON object or exactly one fenced JSON block, optionally
surrounded by explanatory prose. Fences may use matching backticks or tildes and a `json` or empty
language label. Markdown links in surrounding prose are allowed. Other fences, additional JSON
objects or arrays outside the block, duplicate keys,
nonstandard constants and multiple candidates are rejected. It never guesses boundaries from
the first/last brace, merges candidates or repairs malformed JSON.
The extracted object is validated against the complete schema, including conditional and format
constraints, before being emitted to the consumer. Invalid output with native exit 0 becomes exit 1;
native nonzero statuses and timeouts remain failures. No adapter-specific schema/output flags are added.
Success is recorded only after UTF-8 serialization and output write/flush succeed. Serialization
or delivery errors preserve the native output and produce a nonzero diagnostic with the cause.

For schema-bound commands, `command execute --artifacts-dir NEW_DIRECTORY` stores `native.stdout`,
`native.stderr`, and `diagnostic.json` with native/effective exit codes and the reason for failure.
The directory must be new for each attempt. Without the option, a persistent temporary directory
is created and reported on stderr. On failure stdout preserves the original native bytes for the
coordinator's failure logger; on success the original response remains in the artifact directory.
Commands without `output-schema` keep their existing streaming behavior. Old plans must be regenerated.

`execution-policy.workspace` accepts `read-only` or `read-write`. `execution-policy.network` accepts `disabled`,
`enabled` or `auto`. When read-only workspace access or disabled network access is selected, the adapter must enforce
that restriction through native CLI controls or planning stops. Codex explicitly maps workspace `read-write`
to `--sandbox workspace-write`, preserving the network restriction independently. `auto` delegates the choice to the executor.

For Claude Code, read-only commands use non-interactive permission denial, disable editing tools and expose Bash
through fixed wrappers. `.ai-evo/bin/ai-evo-git-read` offers argument-safe `status`, `diff`, `show`, `log`,
`rev-parse`, `merge-base` and `ls-files` operations. This preserves branch and diff inspection without exposing
arbitrary shell commands. The wrapper disables configured Git conversion filters and compares unfiltered
worktree content; `status` and `diff` omit submodules to avoid running helpers from nested repositories.
When explicitly requested by a command, `.ai-evo/bin/ai-evo-github-read` also offers `auth-status`, `repo-view`
and `issue-view <positive-number>` using authenticated `gh` calls for the checkout's repository.
It accepts no arbitrary flags, URLs, API endpoints or mutations, suppresses authentication diagnostics,
disables interactive prompts and bounds each call to 60 seconds. GitHub.com is the supported host.
No general `gh` or Bash grant is added. A network-disabled command or profile blocks planning if a GitHub capability is required.
Network-disabled commands also disable web tools and unconfigured MCP servers while
retaining native edit tools when the workspace policy is read-write.

Commands and steps can declare optional capability lists:

```yaml
execution-policy:
  workspace: read-only
  network: enabled
  capabilities: [github.auth-status, github.repo-view, github.issue-view]
  deny-capabilities: []
```

Each capability is a required operation, not an arbitrary executable name. The adapter's
`capability-translation` maps it to native grants. Only requested operations extend the workspace
allowlist; invocation/session ceilings and all native denies retain precedence. An explicit denial,
disabled network, unknown capability, or a grant excluded by a native ceiling stops planning with
a diagnostic naming the capability. Uncertain overlap with a native deny also stops planning.
An omitted or empty list adds no grants. Deny-only entries are translated to native denies.
Capability plans disable unconfigured MCP servers and use non-interactive permission denial.

The initial mappings support the three GitHub read operations on Claude with `workspace: read-only`.
Codex and read-write capability mappings are not implemented: requests in those modes fail planning.
Existing commands without capability declarations retain their baseline policy. To add support,
implement and verify native enforcement before exposing another adapter mapping; prompt instructions
alone do not satisfy the contract. Rebuild saved plans after changing command declarations or adapters.

Read-write/auto steps do not automatically authorize the host client's permission prompts or paths outside
its allowed directories. A silent CLI can still be waiting for host permissions; inspect native tool results
before attributing a delay to the project script. A coordinator-owned persistence step can use
`executor: current` to avoid a second delegated session, subject to the coordinator's own permissions.

These Bash restrictions also apply to project scripts and test runners named in a command's instructions.
The [script guide](command-scripts.md#adapter-permissions) explains adapter selection for those tasks;
the [runtime-tests example](../examples/runtime-tests/README.md) uses Codex for the script-backed steps.

### Claude policy composition

The core parses Claude invocation, session, effort-profile and execution-policy arguments into structured
permission modes and tool-rule sets before serializing them once. This applies to every command and recipe;
other adapters retain their existing translations. Policy composition does not depend on the order of
workspace and network declarations:

- Each explicit `--tools` list is a capability ceiling: lists intersect. An absent list or `default` imposes
  no ceiling. Fully denied tools are removed from the resulting list.
- Each explicit `--allowedTools` list is an approval ceiling: lists intersect. A bare tool includes its scoped
  rules, so intersecting `Bash` with `Bash(.ai-evo/bin/ai-evo-git-read *)` keeps only the wrapper rule.
  Identical scoped rules survive; different scoped patterns are conservatively omitted when their
  intersection cannot be proved. Grants for unavailable or fully denied tools are removed.
- `--disallowedTools` rules form a union. Deny always wins: an explicit `Bash` or `Bash(*)` deny disables Bash,
  including the wrapper. The core never removes a safety denial to make an allow rule work. Scoped denials
  remain intact even when the broader tool is available; Claude evaluates those denials before approvals.
- Repeated permission modes collapse to one. `dontAsk` prevails over approval-capable modes;
  incompatible modes such as `plan` and `dontAsk` stop planning. Permission prompts collapse to `none`
  when any layer requests it. `--strict-mcp-config` is retained once. Unrelated repeatable options are preserved.
- Empty intersections serialize as `--tools=` or `--allowedTools=`, preserving empty lists without empty
  argv entries or reverting to defaults. Camel-case, hyphenated aliases, inline values and variadic tool
  lists normalize to the same representation; spaces and commas inside scoped rules are preserved.

For read-only, network-disabled review with subagents disabled, the available tools are
`Bash,Glob,Grep,Read`; automatic approvals are `Bash(.ai-evo/bin/ai-evo-git-read *),Glob,Grep,Read`.
`Agent,Edit,NotebookEdit,WebFetch,WebSearch,Write` remain explicitly denied. `dontAsk`, prompt target `none`,
print mode and strict MCP configuration remain active. Network restriction concerns task tools, not the
Claude service connection needed to run the model. Enforcement is provided by Claude permissions and the Git
wrapper, not an additional OS sandbox; local/managed Claude settings and vendor permission behavior still apply.

The core validates built-in names against the supported adapter mapping. Unknown names and obsolete
`MultiEdit`/`Task` entries stop planning with a mapping diagnostic rather than silently discarding a restriction
or forwarding an ineffective deny rule. MCP permission rules remain supported. No runtime version probe or
automatic alias substitution is needed for this fix: planning remains offline and deterministic. Adding a new
built-in tool requires reviewing the mapping against the supported CLI. See the official
[tool reference](https://code.claude.com/docs/en/tools-reference) and
[permission rules](https://code.claude.com/docs/en/permissions).

Built-in adapters declare `prompt-delivery: stdin`. The execution plan exposes this as
`application.prompt_delivery`. For delegated execution, the coordinating AI passes the complete resolved plan
to `command execute` on stdin. The core starts the native CLI and sends the handoff prompt through its stdin;
the coordinator must not launch the delegated CLI separately or append a positional prompt. This avoids
variadic options such as Claude Code's `--disallowedTools <tools...>` consuming the prompt. Custom adapters may
instead declare `argument-before-options` or `argument-after-options` when their CLI requires a positional prompt.

## Internal planner commands

These planning commands are designed primarily for AI consumption and return JSON:

```bash
./.ai-evo/bin/ai-evo-skills profile resolve --adapter codex
./.ai-evo/bin/ai-evo-skills command plan acme-cmd-review --adapter codex --input target=HEAD
./.ai-evo/bin/ai-evo-skills recipe plan acme-recipe-reviewed-change --adapter codex --input target=HEAD
# With the complete plan and result journal supplied as JSON on stdin:
./.ai-evo/bin/ai-evo-skills recipe advance
```

Every command plan and expanded recipe step includes a `handoff` with type `ai-evo-resolved-command`,
resolved planning status, `allow_planning: false` and a snapshot of the skill. Its `with` and `application`
fields are the authoritative inputs, directory, execution policy, profile and native CLI arguments.
Use `recipe advance` to resolve runtime output references in `with` before each recipe step, as described in
the [runtime protocol](recipe-runtime.md). The coordinator sends the complete resolved delegated step JSON
to `.ai-evo/bin/ai-evo-skills command execute` on stdin. This command consumes a trusted local plan; it does
not load or revalidate the catalog and must not be used with untrusted execution JSON. It validates the full
snapshot against the packaged `execution-plan.schema.json`, including policy, profile and session metadata,
and checks cross-field consistency before spawning a process. Regenerate older plans after upgrading;
runtime snapshots are release-specific even though the on-disk project protocol remains `1.0`.
Conditional steps must first pass through `recipe advance`; `command execute` rejects an unresolved `when`.

`command execute` constructs the structured `ai-evo-execution-handoff` prompt and sets
`AI_EVO_EXECUTION_HANDOFF=resolved` for the child. Core CLI calls to `command plan`, `recipe plan`, `recipe advance` or nested
`command execute` are rejected while that marker is present. Delegates perform the task directly, skipping
planning instructions in existing skill text. This prevents accidental replanning through the supported
handoff; it is not an OS security boundary against an executor deliberately removing the marker.
Child stdout/stderr and exit status are preserved, so the coordinator stops the recipe on failure.

## Timeout and cancellation

`command execute --timeout <seconds>` sets a positive finite deadline (default: 900 seconds). Timeout exits
with status 124; SIGINT/SIGTERM exit with 130/143. The deadline includes supervisor startup and both
input transfers; process-tree cleanup has the separate grace periods described below. Cancellation also
works during startup, before a native command can be launched. Slow stdin readers receive the complete
UTF-8 prompt followed by EOF without blocking timeout or cancellation checks.

A private supervisor process acts as a Linux child subreaper and follows descendants even after `setsid` or
double-fork. It sends TERM, allows up to two seconds for graceful exit, then sends KILL and allows up to
two seconds to reap remaining descendants. Cleanup also runs when the native CLI exits normally, so
background jobs cannot outlive the step. The caller's unrelated children and their descendants remain
outside the supervisor, including descendants created or orphaned during execution. pidfds prevent
signalling a different process after PID reuse. This also applies to resume.
A hard kill of the core process itself cannot be intercepted; use normal cancellation signals.

## Session reuse

Codex session persistence is independent of workspace permissions:

| `execution.reuse-session` | Native launch | Allowed reuse |
|---|---|---|
| `never` | `--ephemeral` | None |
| `correction-only` | Persist session; no `--ephemeral` | Correct a failed step |
| `always` | Persist session; no `--ephemeral` | Resume when appropriate |

Capture the native session id from the CLI output. For a failed Codex step, pass its resolved JSON to
`command execute --resume-session <id> --correction`; the same native policy arguments are retained.
With `always`, `--correction` is optional. The coordinator is responsible for associating the id with the
original step and for deciding that a correction is justified. The native CLI needs writable session storage
outside the read-only worktree when persistence is enabled. Adapters declare optional `session-translation`
and `invocation.resume-arguments`; the bundled Codex adapter defines both. Session metadata distinguishes
`resume_permitted` (profile), `resume_supported` (adapter) and `resume_allowed` (both). The bundled Claude
adapter currently does not implement resume through `command execute` and reports it as unavailable.

A restrictive command is delegated even when its executor matches the coordinating AI, because a fresh native
CLI invocation is required to enforce its sandbox and network policy.

## Maintainer verification

Run `uv run --frozen python -m unittest discover -s tests -v` for offline regression tests. The launcher
sandbox test uses Linux Landlock to deny filesystem writes (except `/dev/null`) and skips if unavailable.
Run `AI_EVO_LIVE_TESTS=1 uv run --frozen python -m unittest discover -s tests -p test_live_execution.py -v`
with authenticated Claude and Codex CLIs to verify sequential read-only execution and correction resume
against the same native session id, and Claude native write/network-tool permissions. This opt-in test
makes model requests. Run `AI_EVO_NATIVE_SANDBOX_TESTS=1 uv run --frozen python -m unittest discover -s tests
-p test_native_policy.py -v` to exercise actual Codex sandbox writes and loopback network access without
model requests. These checks skip with an explicit reason when the host forbids the required namespaces;
a skip does not verify enforcement. The read-write case must successfully create a marker.
