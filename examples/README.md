# Examples

Examples are opt-in; `init` does not install them. Start with Acme, then choose the additional workflow
you need. Native AI execution requires authenticated clients; the recovery demo runs without them.

| Example | What it demonstrates |
|---|---|
| [Acme](acme/README.md) | Direct review recipe first; conditional workflow documented as advanced. |
| [Runtime tests](runtime-tests/README.md) | Scripted context detection and conditional test runners; requires your actual wrappers. |
| [Recovery](recovery/README.md) | A new runtime from a verified consecutive prefix, with a runnable synthetic demonstration. |

A **command** is directly invocable, a **step** under `catalog/recipes/_steps` is a recipe-only service, and a
public **recipe** connects them through declared inputs and outputs. A recipe under
`catalog/recipes/_iterations` is an internal composition reached only through another recipe. **Recovery** is
a runtime operation that reuses verified earlier results; it is not a new skill kind or automatic approval of
previous work.
