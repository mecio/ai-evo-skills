"""Recipe naming diagnostics shared by catalog and runtime validation."""
import re


RECIPE_NAME_RE = re.compile(r'[a-z]{3,6}-recipe-[a-z0-9]+(?:-[a-z0-9]+)*')


def recipe_name_error(name: str, namespace: str | None = None) -> str | None:
    """Validate a full recipe name and suggest its explicit migration target."""
    written_namespace, separator, suffix = name.partition('-')
    namespace = namespace or written_namespace
    if (RECIPE_NAME_RE.fullmatch(name) and name.startswith(namespace + '-recipe-')
            and len(name) <= 64):
        return None
    if not separator:
        suffix = name
    if suffix.startswith('recipe-'):
        suffix = suffix[len('recipe-'):]
    expected = f'{namespace}-recipe-{suffix or "<name>"}'
    return (f'invalid recipe name {name!r}; expected {expected!r} '
            '(format <namespace>-recipe-<name>, at most 64 characters; shorten the name if needed)')
