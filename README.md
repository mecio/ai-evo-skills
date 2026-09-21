# AI Evo Skills

**License:** Apache-2.0 · **Status:** public beta, Linux-first

AI Evo Skills turns proven prompts into reusable skills with standardized inputs and execution policies.
Teams maintain those skills in one shared catalog and compose workflows where Codex and Claude Code can
delegate tasks, exchange results and act on each other's feedback. Once a prompt is captured in a skill,
developers invoke it and supply only the inputs needed for the task, without rewriting or pasting the same
instructions each time.

For example, save your team's review criteria once, then invoke `acme-cmd-review` with a Git target and a focus.
A recipe can ask Claude to perform that review, pass its findings to Codex for verification, and send
Codex's feedback back to Claude for a revised report.

[First skill](docs/first-skill.md) · [Recipes](docs/first-skill.md#compose-skills-into-recipes) · [Documentation](#documentation)

## What does it provide?

AI Evo Skills is a small, project-local orchestration layer built on the Agent Skills format:

- **Commands** store atomic operations in a `SKILL.md`, with a prompt, named inputs and execution
  policies. They can be invoked directly or composed in recipes.
- **Steps** live under `skills/catalog/recipes/_steps`, store atomic workflow services that can only be invoked
  by recipes and are not published as native user-facing skills.
- **Recipes** stored directly under `skills/catalog/recipes` are shared entrypoints published to enabled
  clients. They compose commands, steps or other recipes into an ordered workflow, pass results between calls,
  choose executors, validate dependencies and stop at the first failure.
- **Iteration recipes** live under `skills/catalog/recipes/_iterations`, can only be reached through another
  recipe and are not published as native user-facing skills.
- **Adapters** publish the relevant skills into each enabled AI client's native project directory and translate
  common execution policies into its CLI controls. Bundled adapters support Codex and Claude Code.
- **Effort profiles** define shared preferences for reasoning, tests, resource use and reporting.

The engine supplies the CLI, schemas, adapters and templates. Your project supplies the prompts, directives
and catalog. Initialization creates the structure and a default effort profile; you author the actual skills.

```text
skills/catalog/
├── commands/                   published shared commands
└── recipes/
    ├── <namespace>-recipe-*/   published shared recipe entrypoints
    ├── _steps/                 atomic recipe-only services
    └── _iterations/            nested technical recipes
```

The underscore collections are implementation details of recipes. The engine resolves their contents while
planning a public or personal recipe, but `sync` never publishes them as native skills. A recipe in
`_iterations` also cannot be used as the root of `recipe plan`.

Commands can also call project scripts for deterministic decisions and checks. For example, a script can
identify a worktree's runtime, a recipe can select the applicable test suites, and an AI can interpret
their results. See the [script guide and use cases](docs/command-scripts.md) and
[runtime-tests example](examples/runtime-tests/README.md).

## Multiple AIs, one workflow

**The AI where you invoke a recipe coordinates the work.** Start it in Codex and Codex orchestrates;
start it in Claude Code and Claude orchestrates. The recipe selects the executor for each step.
The coordinator sends that executor the task instructions, resolved inputs and execution policies,
then records its output and passes the declared results to subsequent steps.

This lets one AI direct another using its previous response. For example, Codex can coordinate a recipe
that asks Claude for a review, uses a Codex step to check the findings, and asks Claude to revise the
report using that feedback:

```mermaid
flowchart LR
    A[Claude: review] -->|Review findings| B[Codex: verify]
    B -->|Corrections and feedback| C[Claude: revise report]
    A -->|Original review| C
```

The recipe makes those exchanges explicit. This illustrative `steps` excerpt assumes you have authored
the three commands with the inputs shown:

```yaml
steps:
  - id: review
    uses: acme-cmd-review
    executor: claude
    with:
      target: HEAD
  - id: verify
    uses: acme-cmd-verify
    executor: codex
    with:
      target: HEAD
      review: "${{ steps.review.output }}"
  - id: revise
    uses: acme-cmd-revise-review
    executor: claude
    with:
      review: "${{ steps.review.output }}"
      feedback: "${{ steps.verify.output }}"
```

`executor` chooses who does the work; `${{ steps.verify.output }}` passes that step's complete result
as an input to another command. The coordinator manages these exchanges through the engine.
Each executor receives the task and inputs supplied for its step; conversation history is not automatically shared.

**Feedback rounds must be declared in the recipe.** Steps run in order and can consume earlier outputs.
A further review or correction requires a further step; the workflow does not automatically repeat until
an AI is satisfied. See the [recipe walkthrough](docs/first-skill.md#compose-skills-into-recipes) for a
complete recipe and [executor selection](docs/authoring.md#executor-selection) for delegation rules.

## When is it useful?

Use it when a team wants to preserve established prompts, share improvements in one place, run the same skill
across AI clients, or compose recurring tasks such as review, verification and reporting. Personal workflows
can reuse shared commands through recipes in a local, Git-ignored collection.

A single native skill is sufficient for one short operation that needs no shared validation or orchestration.
AI Evo Skills standardizes instructions and execution contracts; AI-generated results still require judgment
and review.

| Existing mechanism | What AI Evo Skills adds |
|---|---|
| Native Agent Skills | Formal inputs, recipes, shared profiles and validation |
| Vendor skill directories | One canonical catalog published to enabled clients |
| `AGENTS.md` and `CLAUDE.md` | Task-specific operations alongside persistent project guidance |
| MCP servers and plugins | Workflows whose skills can use connected tools, subject to execution policies |
| Scripts and CI | Orchestration for prompt-driven steps that need AI judgment |

## Requirements

The engine targets Linux and requires:

- Git and symbolic-link support;
- Python 3.11 or newer;
- [uv](https://docs.astral.sh/uv/getting-started/installation/);
- each enabled AI CLI installed and authenticated;
- for delegated execution, Linux kernel 5.3+ with accessible procfs, pidfds and child-subreaper support.

See the [execution reference](docs/execution.md#verified-adapter-versions) for verified adapter versions.
This README describes the current checkout; [CHANGELOG.md](CHANGELOG.md) distinguishes unreleased changes
from published releases.

## Get started

Follow the [first skill walkthrough](docs/first-skill.md) to install the engine, save your prompt as a command,
validate it and publish it to your AI clients. The guide includes a complete `acme-cmd-review` skill and recipe
examples. Initialization creates the project structure; skills become available after you author and synchronize them.

Once the example skill is published, invoke it in Codex with:

```text
$acme-cmd-review target=HEAD focus=security
```

Claude Code uses `/acme-cmd-review target=HEAD focus=security`. The review criteria stay in the shared skill;
only the inputs change between invocations.

> [!TIP]
> Store recurring choices in a skill or recipe to shorten the invocation. For example, a recipe named
> `acme-recipe-review-security-head` can fix `target=HEAD` and `focus=security`, so you invoke it simply as
> `$acme-recipe-review-security-head`. See the [complete example and default options](docs/first-skill.md#shorter-invocations-with-fixed-choices).

## How execution works

```mermaid
flowchart LR
    A[Shared prompt catalog] --> B[validate and sync]
    B --> C[Native skill invocation]
    C --> D[Apply inputs and execution policies]
    D --> E[Run task or sequential recipe]
```

The engine validates the catalog and publishes commands and directly invocable recipes to enabled clients.
Recipe-only steps and iteration recipes remain internal to the catalog and are embedded in resolved recipe
plans. The AI resolves the invocation and runs the task under its declared policies; recipes pass results
between steps and stop on failure.
See the [execution reference](docs/execution.md) for delegation, native restrictions and session handling.

## Documentation

- [Examples index](examples/README.md): commands, internal steps, recipes and recovery.
- [Acme starter catalog](examples/acme/README.md): three commands, a script-backed internal step and two recipes.
- [Recovery example](examples/recovery/README.md): verified-prefix recovery with an isolated demo and real-run instructions.
- [Runtime-tests example](examples/runtime-tests/README.md): scripted PHP context detection, conditional suites
  and reporting; supply your application's test wrappers and worktree mapping.
- [Commands that use scripts](docs/command-scripts.md): placement, output contracts, adapter permissions and
  an inventory of Enabu workflows and script callers.
- [First skill walkthrough](docs/first-skill.md): installation, a complete review prompt, publication,
  shorter invocations and recipe examples.
- [Project setup and publication](docs/project-setup.md): directory layout, initialization, configuration,
  shared worktrees and validation boundaries.
- [Authoring commands, recipes and profiles](docs/authoring.md): artifact creation, input contracts and
  effort profile settings.
- [Execution and adapters](docs/execution.md): internal CLI, native restrictions, process supervision,
  session reuse and maintainer verification.
- [Recipe runtime](docs/recipe-runtime.md): conditions, sequential iteration, input and output resolution, journals and skips.
- [Recipe naming migration](docs/recipe-naming-migration.md): naming rules and manual migration steps.
- [Changelog](CHANGELOG.md): unreleased changes and release history.

## License

Maintained by [Graziano Ugenti](https://github.com/mecio). Copyright 2026 Graziano Ugenti.

AI Evo Skills is released under the [Apache License 2.0](LICENSE). It may be used, modified and distributed,
including in commercial and proprietary products, subject to the license conditions. Attribution notices are
recorded in [NOTICE](NOTICE).

## References

- [Agent Skills overview](https://agentskills.io/home)
- [Agent Skills specification](https://agentskills.io/specification)
- [Codex skill locations and symbolic-link support](https://learn.chatgpt.com/docs/build-skills)
- [Claude Code CLI reference](https://code.claude.com/docs/en/cli-usage)
