# Migrate recipe names

All shared and personal recipes now use `<namespace>-recipe-<name>`. New commands use `<namespace>-cmd-<name>`; see [command authoring](authoring.md#create-artifacts).
This beta change intentionally rejects old recipe names. It does not introduce aliases, install two names,
or silently rewrite files. The change is released in engine `0.1.0-beta.3`; see the
[release changelog](../CHANGELOG.md#010-beta3).

## Manual migration

For example, migrate `acme-reviewed-change` to `acme-recipe-reviewed-change`:

1. Rename its directory under `skills/catalog/recipes` or `skills/custom/recipes`. Keep only the new directory.
2. Change `name` in both `SKILL.md` frontmatter and `recipe.yaml` to the new directory name.
3. Update every `uses` reference to that recipe, including references in other shared and personal recipes.
   Keep references to atomic commands unchanged. Update planner commands, native invocations, scripts and
   documentation that mention the old name, including the procedure and examples inside `SKILL.md`.
4. Run `.ai-evo/bin/ai-evo-skills validate`. An invalid old name reports the expected new name. If adding the
   marker would exceed 64 characters, choose a shorter suffix and update all references consistently.
5. Run `sync --dry-run` and review the removals and new links, then run `sync` in each application worktree.
   Old managed links are removed even if their former source directory is now missing. Unmanaged files and
   links are preserved; resolve reported collisions explicitly. Do not leave aliases for the old recipe name.
6. Regenerate recipe execution plans and start a fresh result journal. `recipe advance` rejects snapshots
   whose root recipe name still uses the old convention. Do not rename records in a running execution.

If several worktrees share the specification repository, rename shared recipe sources once and synchronize
each worktree separately. Personal recipes also require migration and may contain references to shared recipes;
include them even though they are ignored by Git.

`create recipe reviewed-change` now generates `acme-recipe-reviewed-change` directly. With `--catalog` it uses
the shared catalog; otherwise it uses personal recipes. Supply neither `recipe-` nor a namespace to `create`.
Already prefixed names are errors with a suggested short name. An explicitly foreign full recipe name such
as `other-recipe-reviewed-change` is rejected rather than imported or renamed automatically.

The [Acme starter catalog](../examples/acme/README.md) demonstrates the current naming convention.
Renaming existing recipes preserves conditions, step ids, output references, execution policies and command names.

## Short names accepted by the CLI

`create recipe` accepts only the short name and adds the namespace and `recipe-` exactly once:

| Input in namespace `acme` | Result |
|---|---|
| `my-review` | Creates `acme-recipe-my-review` in `custom/recipes`. |
| `my-review --catalog` | Creates `acme-recipe-my-review` in `catalog/recipes`. |
| `recipe-my-review` | Error; pass `my-review`. |
| `acme-recipe-my-review` or `acme-my-review` | Error; pass `my-review`. |
| `demo-recipe-my-review` | Namespace mismatch error; pass the short name explicitly to create it under `acme`. |

Repeated leading `recipe-` markers are also rejected, with a short-name suggestion. A foreign full recipe
name is recognized by `<other-namespace>-recipe-`; ordinary hyphenated names such as `team-review` remain
short names. A name such as `demo-my-review`, without the recipe marker and without the current namespace,
is treated literally as a short name: the CLI cannot infer another project's namespace from arbitrary words.

Legacy recipe names are rejected with the expected name; validation and synchronization never rename
artifacts or create compatibility aliases. Follow the [manual migration steps](#manual-migration)
before using existing recipes with this engine checkout.

## Protocol and engine compatibility

This is a stricter engine naming rule within the current beta, not a new wire or storage format. YAML/JSON
field shapes and on-disk protocol `1.0` are unchanged. Older engines can read the new names, but only the updated
engine enforces the convention. New engines reject legacy recipe names, including already planned recipe
snapshots. There is no implicit migration based on a protocol number. Adopt the engine, renamed sources and
updated coordinator instructions together when upgrading to `0.1.0-beta.3`.
