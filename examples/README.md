# Examples

Examples are opt-in; `init` does not install them. Start with Acme, then choose the additional workflow
you need. Native AI execution requires authenticated clients; the recovery demo runs without them.

| Example | What it demonstrates |
|---|---|
| [Acme](acme/README.md) | Public commands, an internal script-backed step, sequential and conditional recipes. |
| [Runtime tests](runtime-tests/README.md) | Scripted context detection and conditional test runners; requires your actual wrappers. |
| [Recovery](recovery/README.md) | A new runtime from a verified consecutive prefix, with a runnable synthetic demonstration. |

A **command** is directly invocable, a **step** is a recipe-only service, and a **recipe** connects them
through declared inputs and outputs. **Recovery** is a runtime operation that reuses verified earlier
results; it is not a new skill kind or automatic approval of previous work.
