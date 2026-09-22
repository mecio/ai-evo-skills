"""Exercise real planning and recovery with explicitly synthetic AI results in a temporary repository."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ENGINE = Path(__file__).resolve().parents[2]
RECIPE = 'acme-recipe-reviewed-change'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--invalidate-review', action='store_true', help='Simulate changed review dependencies')
    args = parser.parse_args()
    env = {**os.environ, 'PYTHONPATH': str(ENGINE / 'tooling/src')}
    with tempfile.TemporaryDirectory(prefix='ai-evo-recovery-example-') as temporary:
        root = Path(temporary)
        subprocess.run(['git', 'init', '-q'], cwd=root, check=True)
        (root / '.ai-evo').symlink_to(ENGINE, target_is_directory=True)

        def cli(*arguments, payload=None, expected_exit=0):
            result = subprocess.run([sys.executable, '-m', 'ai_evo_skills.cli', *arguments],
                                    cwd=root, env=env, input=json.dumps(payload) if payload is not None else None,
                                    text=True, capture_output=True)
            if result.returncode != expected_exit:
                raise RuntimeError(result.stderr or result.stdout)
            return result.stdout

        cli('init', '--namespace', 'acme', '--adapter', 'codex')
        example = ENGINE / 'examples/acme'
        shutil.copytree(example / 'catalog', root / '.ai-evo-prj/skills/catalog', dirs_exist_ok=True)
        shutil.copytree(example / 'scripts', root / '.ai-evo-prj/scripts')
        cli('validate')
        cli('sync', '--dry-run')

        plan = json.loads(cli('recipe', 'plan', RECIPE, '--adapter', 'codex'))
        source = {'plan': plan, 'results': []}
        review = 'SIMULATED review: fixture text, no repository inspection or AI execution.\n'
        source['results'].append({'step': 'review', 'status': 'succeeded', 'output': review})
        # Deliberate fixture failure, not the outcome of an actual report command.
        source['results'].append({'step': 'report', 'status': 'failed', 'exit_code': 1})
        if json.loads(cli('recipe', 'advance', payload=source, expected_exit=1))['status'] != 'failed':
            raise RuntimeError('source fixture must stop on failure')
        source_file = root / 'previous/state.json'
        source_file.parent.mkdir()
        source_file.write_text(json.dumps(source), encoding='utf-8')
        original = source_file.read_bytes()
        target_file = root / 'new-plan.json'
        target_file.write_text(cli('recipe', 'plan', RECIPE, '--adapter', 'codex'), encoding='utf-8')
        common = ['recipe', 'recover', '--source-state', str(source_file), '--plan', str(target_file)]
        evidence = json.loads(cli(*common, '--inspect'))
        for check in evidence['checks']:
            # Only synthetic fixtures permit this shortcut. Real runs require historical/current evidence.
            check.update(valid=True, reason='Synthetic fixture only: unchanged in this isolated demo',
                         source_dependencies={'fixture': 'v1'}, current_dependencies={'fixture': 'v1'})
        if args.invalidate_review:
            evidence['checks'][0]['current_dependencies']['fixture'] = 'v2'
        evidence_file = root / 'evidence.json'
        evidence_file.write_text(json.dumps(evidence), encoding='utf-8')
        destination = root / 'new-runtime'
        cli(*common, '--evidence', str(evidence_file), '--output-dir', str(destination))
        state = json.loads((destination / 'state.json').read_text())
        report = json.loads((destination / 'recovery.json').read_text())
        transition = json.loads(cli('recipe', 'advance', payload=state))
        if source_file.read_bytes() != original:
            raise RuntimeError('source state changed')
        expected = 'review' if args.invalidate_review else 'report'
        if transition['status'] != 'ready' or transition['step']['id'] != expected:
            raise RuntimeError('recovery selected an unexpected next step')
        print(json.dumps({'simulated': True, 'recovered_steps': [r['step'] for r in state['results']],
                          'next_step': expected, 'stop_reason': report['stop_reason'],
                          'source_unchanged': True}, indent=2))


if __name__ == '__main__':
    main()
