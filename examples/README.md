# Examples

Examples are documentation only and are never installed by `init`. Start from the templates to build atomic
commands and compose them into sequential recipes owned by the project.

`review-flow/` shows two shared atomic commands and one personal sequential recipe. Copy the relevant files
into the matching directories under `.ai-evo-prj/skills`, replace the `demo` namespace with the project's
configured namespace, then run `validate` and `sync`.

The example also demonstrates both variable forms:

- `${{ inputs.target }}` reads a recipe input;
- `${{ steps.review.output }}` reads the output of an earlier step.

Step outputs can only be consumed by later steps. Forward references and cycles are validation errors.

[`php-context/`](php-context/README.md) provides a complete conditional recipe: PHP 7.2 runs legacy tests;
PHP 8.3 runs legacy and Unit tests. A final command aggregates both branches, including a structured skip
serialized as a string input when Unit tests are omitted. It uses the core `recipe advance` coordinator loop.
