# <namespace> AI entrypoint

Before working on the project, preserve existing changes and read only the project directives relevant to the
current task. Use the component map as an index and verify behavior against source code, manifests and tests.

Name every recipe `<namespace>-recipe-<name>`; name new commands `<namespace>-cmd-<name>`. Use complete
skill names in planner calls and `uses` references. Pass only `<name>` to `create command` and `create recipe`;
do not add aliases for old recipe names.

When coordinating recipes, use `.ai-evo/bin/ai-evo-skills recipe advance` with the planned recipe and ordered
result journal before executing each step. It evaluates conditions and resolves skipped outputs. Skip records
are not failures; stop on execution or runtime validation failures. See `.ai-evo/docs/recipe-runtime.md`.
