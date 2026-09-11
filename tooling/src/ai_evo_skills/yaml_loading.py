"""Safe YAML loading with explicit duplicate-key diagnostics."""
from typing import Any

import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode


class StrictSafeLoader(yaml.SafeLoader):
    def __init__(self, stream):
        super().__init__(stream)
        self._checked_mappings: set[int] = set()

    def flatten_mapping(self, node: MappingNode) -> None:
        # Check the written keys before merges are expanded. An explicit override
        # of a merged default is valid, but two explicit keys are not. Anchors may
        # revisit a mapping that has already been flattened.
        if id(node) not in self._checked_mappings:
            self._checked_mappings.add(id(node))
            seen = {}
            for key_node, _ in node.value:
                key = '<<' if key_node.tag == 'tag:yaml.org,2002:merge' else self.construct_object(key_node)
                try:
                    duplicate = key in seen
                except TypeError as exc:
                    raise ConstructorError('while constructing a mapping', node.start_mark,
                                           'found unhashable key', key_node.start_mark) from exc
                if duplicate:
                    raise ConstructorError('while constructing a mapping', node.start_mark,
                                           f'duplicate key {key!r}', key_node.start_mark)
                seen[key] = key_node.start_mark
        super().flatten_mapping(node)


def load_strict_yaml(text: str) -> Any:
    return yaml.load(text, Loader=StrictSafeLoader)
