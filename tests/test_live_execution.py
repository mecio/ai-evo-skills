"""Opt-in tests against authenticated native CLIs; may consume account usage."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import unittest

import yaml
import test_cli as fixtures


@unittest.skipUnless(os.environ.get('AI_EVO_LIVE_TESTS') == '1', 'set AI_EVO_LIVE_TESTS=1 for authenticated native CLI tests')
class LiveExecutionTest(unittest.TestCase):
    repository = fixtures.CliIntegrationTest.repository
    initialize = fixtures.CliIntegrationTest.initialize
    add_command = fixtures.CliIntegrationTest.add_command
    run_cli = fixtures.CliIntegrationTest.run_cli

    def native_execute(self, root, step, *arguments):
        result = subprocess.run(
            fixtures.COMMAND + ['command', 'execute', '--timeout', '60', *arguments],
            cwd=root, env=fixtures.CLI_ENV, input=json.dumps(step),
            text=True, capture_output=True, timeout=90,
        )
        self.assertEqual(0, result.returncode, result.stderr[-3000:])
        return result

    def test_read_only_claude_codex_recipe_and_native_correction_resume(self):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, 'codex', 'claude')
            self.add_command(root)
            first = root / '.ai-evo-prj/skills/catalog/commands/abc-inspect/SKILL.md'
            first.write_text(fixtures.VALID_COMMAND.replace('executor: current', 'executor: claude').replace(
                '1. Inspect.', '1. Return exactly CLAUDE_OK without calling any tools.'
            ))
            second = first.parent.parent / 'abc-verify/SKILL.md'
            second.parent.mkdir()
            second.write_text(fixtures.VALID_COMMAND.replace('abc-inspect', 'abc-verify').replace(
                'executor: current', 'executor: codex'
            ).replace('inputs: {}', 'inputs:\n  review:\n    description: Prior result\n    required: true').replace(
                '1. Inspect.', '1. Run `.ai-evo/bin/ai-evo-skills command plan abc-verify --adapter codex`.\n2. For this regression, return CORRECTION_REQUIRED on the initial turn. When the core handoff correction field is true, return exactly CODEX_OK if the review includes CLAUDE_OK.'
            ))
            recipe = root / '.ai-evo-prj/skills/catalog/recipes/abc-flow'
            recipe.mkdir()
            (recipe / 'SKILL.md').write_text(fixtures.VALID_FLOW_SKILL)
            (recipe / 'recipe.yaml').write_text(yaml.safe_dump({
                'version': '1.0', 'name': 'abc-flow', 'executor': 'codex', 'inputs': {},
                'steps': [{'id': 'review', 'uses': 'abc-inspect'}, {'id': 'verify', 'uses': 'abc-verify', 'with': {'review': '${{ steps.review.output }}'}}],
                'outputs': {'result': {'value': '${{ steps.verify.output }}'}},
            }))
            result = self.run_cli(root, 'recipe', 'plan', 'abc-flow', '--adapter', 'codex')
            self.assertEqual(0, result.returncode, result.stderr)
            steps = json.loads(result.stdout)['execution']['steps']
            before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file() and '.git' not in p.parts}
            first_result = self.native_execute(root, steps[0])
            self.assertIn('CLAUDE_OK', first_result.stdout)
            steps[1]['with']['review'] = first_result.stdout.strip()
            steps[1]['application']['cli_arguments'].append('--json')
            self.assertNotIn('--ephemeral', steps[1]['application']['cli_arguments'])
            second_result = self.native_execute(root, steps[1])
            events = [json.loads(line) for line in second_result.stdout.splitlines() if line.startswith('{')]
            session_id = next(e['thread_id'] for e in events if e.get('type') == 'thread.started')
            self.assertIn('CORRECTION_REQUIRED', second_result.stdout)
            self.assertFalse(any(e.get('item', {}).get('type') == 'command_execution' for e in events))
            # Treat the initial result as a failed output check, then correct the same persisted thread.
            resumed = self.native_execute(root, steps[1], '--resume-session', session_id, '--correction')
            resumed_events = [json.loads(line) for line in resumed.stdout.splitlines() if line.startswith('{')]
            self.assertEqual(session_id, next(e['thread_id'] for e in resumed_events if e.get('type') == 'thread.started'))
            self.assertIn('CODEX_OK', resumed.stdout)
            self.assertNotIn('no rollout found', resumed.stderr)
            after = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file() and '.git' not in p.parts}
            self.assertEqual(before, after)

    def test_claude_native_write_and_network_tool_permissions(self):
        import http.server
        import threading
        import urllib.request

        requests = []
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append(self.path)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'probe')
            def log_message(self, *_):
                pass

        temporary, root = self.repository()
        with temporary, http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                url = f'http://127.0.0.1:{server.server_port}/probe'
                with urllib.request.urlopen(url, timeout=2) as response:
                    self.assertEqual(200, response.status)
                baseline = len(requests)
                self.initialize(root, 'claude')
                self.add_command(root)
                skill = root / '.ai-evo-prj/skills/catalog/commands/abc-inspect/SKILL.md'
                for workspace in ('read-only', 'read-write'):
                    marker = root / 'native-marker'
                    body = fixtures.VALID_COMMAND.replace('workspace: read-only', f'workspace: {workspace}')
                    body = body.replace('1. Inspect.', f'1. Try the native Write tool to create {marker} containing POLICY_OK. Try WebFetch on {url}. If a tool is unavailable or denied, report it and do not bypass the restriction. Return POLICY_DONE.')
                    skill.write_text(body)
                    plan = self.run_cli(root, 'command', 'plan', 'abc-inspect', '--adapter', 'claude')
                    self.assertEqual(0, plan.returncode, plan.stderr)
                    result = self.native_execute(root, json.loads(plan.stdout))
                    self.assertIn('POLICY_DONE', result.stdout)
                    self.assertEqual(workspace == 'read-write', marker.exists(), result.stdout)
                    if marker.exists():
                        self.assertIn('POLICY_OK', marker.read_text())
                    self.assertEqual(baseline, len(requests), 'network-disabled executor reached the endpoint')
            finally:
                server.shutdown()
                worker.join(timeout=2)
