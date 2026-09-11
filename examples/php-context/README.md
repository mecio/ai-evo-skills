# Select PHP 7.2 or PHP 8.3 tests

This complete example uses namespace `enabu`. Copy `catalog/` into `.ai-evo-prj/skills/catalog/` in an
initialized project with Codex and Claude enabled. Replace the namespace consistently if needed, then run
`validate`. Either client can coordinate `enabu-php-tests`; the test commands explicitly delegate to Codex.
Examples are never installed automatically.

Prerequisites: `composer.json` declares `config.platform.php` as a 7.2 or 8.3 version and defines
`test:legacy` and `test:unit` scripts. The project environment used by Composer must match that declaration;
the declaration itself does not change the installed PHP executable. Dependencies must already be installed.
Adapt these atomic command procedures to the application's container or PHP launcher before using them.

The [recipe](catalog/recipes/enabu-php-tests/recipe.yaml) runs:

1. `enabu-detect-php-context`, returning exactly `php72` or `php83`.
2. `enabu-test-legacy` unconditionally.
3. `enabu-test-unit` only when the detector output equals `php83`.
4. `enabu-aggregate-php-tests`, reporting both outcomes, including Unit skips on PHP 7.2.

```yaml
steps:
  - id: php_context
    uses: enabu-detect-php-context
  - id: legacy_tests
    uses: enabu-test-legacy
  - id: unit_tests
    uses: enabu-test-unit
    when:
      value: "${{ steps.php_context.output }}"
      equals: "php83"
  - id: summary
    uses: enabu-aggregate-php-tests
    with:
      legacy: "${{ steps.legacy_tests.output }}"
      unit: "${{ steps.unit_tests.output }}"
```

For an input-based alternative, declare a recipe input such as
`php: {description: PHP context, required: true}` and use `value: "${{ inputs.php }}"` in `when`.

The coordinator plans once and calls `recipe advance` with the complete plan and ordered result journal
before each execution. For PHP 7.2, the Unit transition is `skipped`; no Unit command starts, and the summary's
`unit` input is the JSON string representation of:

```json
{"type":"ai-evo-step-skipped","step":"unit_tests","reason":"condition-false"}
```

For PHP 8.3, the Unit transition is `ready` and the summary receives its complete string output. If either
executed test suite fails, fail-fast stops the recipe before the summary. Skipping Unit tests alone does not
stop the recipe. A final result could instead reference `unit_tests`; PHP 7.2 would then return the structured
skip object as the final output.

Comparison is exact. `php83\n` differs from `php83`: detectors and coordinators must honor the complete-output
contract, and coordinators must not trim or guess a value. The example's automated tests validate both plans
and exercise both branches using controlled local executors; they do not run an application's real PHP suites.
See [the runtime protocol](../../docs/recipe-runtime.md) for journal shapes and error behavior.
