#!/usr/bin/env python3
"""Resolve a configured Git worktree to a PHP context without guessing its runtime."""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--config', type=Path,
        default=Path(__file__).resolve().parent.parent / 'skills/config/acme-worktrees.json',
    )
    parser.add_argument('--field', choices=['context'])
    args = parser.parse_args()
    try:
        config = json.loads(args.config.read_text(encoding='utf-8'))
        if not isinstance(config, dict) or config.get('schema_version') != 1:
            raise ValueError('expected schema_version 1')
        entries = config.get('worktrees')
        if not isinstance(entries, list) or not entries:
            raise ValueError('worktrees must be a non-empty array')
        contexts = {}
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError('each worktree must be an object')
            root, context = entry.get('root'), entry.get('context')
            if not isinstance(root, str) or not Path(root).is_absolute():
                raise ValueError('each root must be an absolute path')
            if context not in ('php72', 'php83'):
                raise ValueError('context must be php72 or php83')
            normalized = str(Path(root).resolve())
            if normalized in contexts:
                raise ValueError('multiple entries resolve to the same worktree root')
            contexts[normalized] = context
        result = subprocess.run(
            ['git', 'rev-parse', '--show-toplevel'],
            capture_output=True, text=True, check=True, timeout=10,
        )
        actual_root = str(Path(result.stdout.rstrip('\n')).resolve())
        if actual_root not in contexts:
            raise ValueError(f'unconfigured worktree root: {actual_root}')
        data = {'schema_version': 1, 'git_root': actual_root, 'context': contexts[actual_root]}
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 1
    print(data['context'] if args.field else json.dumps(data, sort_keys=True, separators=(',', ':')))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
