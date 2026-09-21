"""Validate only the presence and UTF-8 encoding of a review, preserving bytes."""
import argparse
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    args = parser.parse_args()
    try:
        content = args.input.read_bytes()
        if not content.decode('utf-8').strip():
            raise ValueError('review output is empty')
    except (OSError, ValueError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 1
    sys.stdout.buffer.write(content)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
