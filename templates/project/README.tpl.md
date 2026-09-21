# <namespace> AI project configuration

This directory contains the directives, skills and profiles owned by the project.

Shared commands live under `skills/catalog/commands` and shared recipe entrypoints directly under
`skills/catalog/recipes`. Recipe-only steps belong to `skills/catalog/recipes/_steps`; nested technical recipes
belong to `skills/catalog/recipes/_iterations`. The underscore collections are validated and expanded through
parent recipes but are not published as native skills.
