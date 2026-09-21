import copy
import json
import io
from pathlib import Path
import subprocess
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import test_cli as fixtures
from ai_evo_skills.execution import ExecutionError, validate_plan


SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object", "additionalProperties": False,
    "required": ["status", "items"],
    "properties": {"status": {"const": "ready"}, "items": {"type": "array", "minItems": 1, "items": {"type": "string"}}},
}
VALUE = {"status": "ready", "items": ["evidence"]}


class OutputContractTest(unittest.TestCase):
    repository = fixtures.CliIntegrationTest.repository
    initialize = fixtures.CliIntegrationTest.initialize
    add_command = fixtures.CliIntegrationTest.add_command
    run_cli = fixtures.CliIntegrationTest.run_cli

    def prepare(self, root):
        self.initialize(root, "claude", "codex")
        self.add_command(root)
        skill = root / ".ai-evo-prj/skills/catalog/commands/abc-inspect/SKILL.md"
        refs = skill.parent / "references"
        refs.mkdir(exist_ok=True)
        (refs / "output.json").write_text(json.dumps(SCHEMA))
        skill.write_text(fixtures.VALID_COMMAND.replace("inputs: {}", "output-schema: references/output.json\ninputs: {}"))
        result = self.run_cli(root, "command", "plan", "abc-inspect", "--adapter", "claude")
        self.assertEqual(0, result.returncode, result.stderr)
        return skill, json.loads(result.stdout)

    def execute(self, root, plan, raw, directory, status=0, timeout=None):
        plan = copy.deepcopy(plan)
        code = "import sys,time; sys.stdin.read(); sys.stdout.buffer.write(" + repr(raw) + "); sys.stdout.flush(); sys.stderr.write('native diagnostic\\n'); sys.stderr.flush(); "
        code += "time.sleep(5)" if timeout else f"sys.exit({status})"
        plan["application"]["command"] = [sys.executable, "-c", code]
        arguments = ["--artifacts-dir", str(directory)] + (["--timeout", str(timeout)] if timeout else [])
        return subprocess.run(fixtures.COMMAND + ["command", "execute", *arguments], cwd=root,
                              env=fixtures.CLI_ENV, input=json.dumps(plan).encode(), capture_output=True)

    def test_schema_snapshot_and_plain_or_fenced_json(self):
        temporary, root = self.repository()
        with temporary:
            skill, plan = self.prepare(root)
            validate_plan(plan)
            app = plan["application"]
            self.assertEqual(SCHEMA, app["output_contract"]["schema"])
            self.assertNotIn("--json-schema", app["cli_arguments"])
            self.assertNotIn("--output-format", app["cli_arguments"])
            supported = self.run_cli(root, "command", "plan", "abc-inspect", "--adapter", "codex")
            self.assertEqual(0, supported.returncode, supported.stderr)
            broken = copy.deepcopy(plan)
            broken["application"]["output_contract"]["schema"] = {"type": "invalid"}
            with self.assertRaisesRegex(ExecutionError, "invalid output schema"):
                validate_plan(broken)
            (skill.parent / "references/output.json").unlink()
            plain = json.dumps(VALUE).encode()
            for index, raw in enumerate((plain, b'Here is the manifest:\n```json\n'+plain+b'\n```\nDone.',
                                         b'Fonte: [GitHub](https://github.com/example/project/issues/1)\n```json\n'+plain+b'\n```\n[Fine]',
                                         b'```\r\n'+plain+b'\r\n```\r\n')):
                directory = root / f"attempt-{index}"
                output = self.execute(root, plan, raw, directory)
                self.assertEqual(0, output.returncode, output.stderr)
                self.assertEqual(VALUE, json.loads(output.stdout))
                self.assertEqual(raw, (directory / "native.stdout").read_bytes())
                self.assertEqual(b"native diagnostic\n", (directory / "native.stderr").read_bytes())
                diagnostic = json.loads((directory / "diagnostic.json").read_text())
                self.assertEqual(0, diagnostic["native_exit_code"])
                self.assertEqual(0, diagnostic["exit_code"])

    def test_invalid_outputs_fail_even_when_native_exit_is_zero_and_preserve_bytes(self):
        temporary, root = self.repository()
        with temporary:
            _, plan = self.prepare(root)
            cases = [
                b'Here is the manifest:\n```json\n{"status":"ready"}\n```\n',
                json.dumps({"status": "ready", "items": []}).encode(),
                b'```json\n{}\n```\n```json\n{}\n```',
                b'{}\n```json\n{}\n```', b'```json\n{}',
                b'Fonte: [GitHub](url) {}\n```json\n'+json.dumps(VALUE).encode()+b'\n```',
                b'```json\n'+json.dumps(VALUE).encode()+b'\n```\n[1,2]',
                b'```python\n{}\n```', b'```json\n{"status":}\n```',
                b'{} {}', b'[]', b'null',
                b'{"type":"result","type":"result"}',
                b'{"value":NaN}', b'\xff', b'',
                b'{"status":"ready","items":["\\ud800"]}',
            ]
            for index, raw in enumerate(cases):
                with self.subTest(index=index):
                    directory = root / f"attempt-{index}"
                    output = self.execute(root, plan, raw, directory)
                    self.assertEqual(1, output.returncode, output.stderr)
                    self.assertEqual(raw, output.stdout)
                    self.assertEqual(raw, (directory / "native.stdout").read_bytes())
                    diagnostic = json.loads((directory / "diagnostic.json").read_text())
                    self.assertEqual(0, diagnostic["native_exit_code"])
                    self.assertEqual("invalid-output", diagnostic["code"])
                    self.assertTrue(diagnostic["message"])
                    self.assertIn(b"invalid-output", output.stderr)
                    self.assertNotIn(b"Traceback", output.stderr)

    def test_delivery_errors_and_flush_precede_success_diagnostic(self):
        from ai_evo_skills.output_contract import execute_structured
        temporary, root = self.repository()
        with temporary:
            raw = json.dumps(VALUE).encode()
            for failure in (None, "write", "flush"):
                directory = root / str(failure)
                testcase = self

                class Consumer(io.BytesIO):
                    def write(self, value):
                        testcase.assertFalse((directory / "diagnostic.json").exists())
                        if failure == "write":
                            raise BrokenPipeError("consumer closed the pipe")
                        return super().write(value)

                    def flush(self):
                        testcase.assertFalse((directory / "diagnostic.json").exists())
                        if failure == "flush":
                            raise OSError("consumer flush failed")
                        return super().flush()

                def native(*args, stdout, stderr, **kwargs):
                    stdout.write(raw)
                    stdout.flush()
                    return 0

                consumer = Consumer()
                with patch("ai_evo_skills.output_contract.run_delegated", side_effect=native), \
                        patch("sys.stdout", SimpleNamespace(buffer=consumer)), \
                        patch("sys.stderr", io.TextIOWrapper(io.BytesIO())):
                    status = execute_structured([], contract={"schema": SCHEMA}, artifacts_dir=directory)
                diagnostic = json.loads((directory / "diagnostic.json").read_text())
                self.assertEqual(1 if failure else 0, status)
                self.assertEqual(status, diagnostic["exit_code"])
                self.assertEqual(0, diagnostic["native_exit_code"])
                self.assertEqual(raw, (directory / "native.stdout").read_bytes())
                if failure:
                    self.assertEqual("output-delivery-failed", diagnostic["code"])
                    self.assertTrue(diagnostic["message"])
                else:
                    self.assertEqual(VALUE, json.loads(consumer.getvalue()))

    def test_nonzero_timeout_and_existing_artifacts_are_preserved(self):
        temporary, root = self.repository()
        with temporary:
            _, plan = self.prepare(root)
            for name, native, timeout, expected in (("failed", 7, None, 7), ("timeout", 0, 0.5, 124)):
                directory = root / name
                result = self.execute(root, plan, b"partial output", directory, status=native, timeout=timeout)
                self.assertEqual(expected, result.returncode, result.stderr)
                self.assertEqual(b"partial output", (directory / "native.stdout").read_bytes())
                diagnostic = json.loads((directory / "diagnostic.json").read_text())
                self.assertEqual(expected, diagnostic["exit_code"])
                self.assertEqual(native if not timeout else None, diagnostic["native_exit_code"])
                retry = self.execute(root, plan, b"overwrite", directory)
                self.assertNotEqual(0, retry.returncode)
                self.assertEqual(b"partial output", (directory / "native.stdout").read_bytes())

    def test_invalid_schema_is_rejected_before_planning(self):
        temporary, root = self.repository()
        with temporary:
            skill, _ = self.prepare(root)
            for schema in ({"type": "invalid"}, {"type": "object", "$ref": "https://example.org/schema"},
                           {"type": "object", "$ref": "#/$defs/missing"}):
                (skill.parent / "references/output.json").write_text(json.dumps(schema))
                result = self.run_cli(root, "command", "plan", "abc-inspect", "--adapter", "claude")
                self.assertNotEqual(0, result.returncode)
                self.assertEqual("", result.stdout)
                self.assertNotIn("Traceback", result.stderr)

    def test_array_contract_uses_same_extractor_and_preserves_evidence(self):
        temporary, root = self.repository()
        with temporary:
            skill, _ = self.prepare(root)
            schema = {'type': 'array', 'items': SCHEMA}
            (skill.parent / 'references/output.json').write_text(json.dumps(schema))
            planned = self.run_cli(root, 'command', 'plan', 'abc-inspect', '--adapter', 'claude')
            self.assertEqual(0, planned.returncode, planned.stderr)
            plan = json.loads(planned.stdout)
            self.assertEqual('json-array', plan['application']['output_contract']['format'])
            validate_plan(plan)
            broken = copy.deepcopy(plan)
            broken['application']['output_contract']['format'] = 'json-object'
            with self.assertRaisesRegex(ExecutionError, 'format must match'):
                validate_plan(broken)
            raw = json.dumps([VALUE]).encode()
            fenced = b'Intro\n```json\n' + raw + b'\n```\nEnd'
            cases = [(raw, True), (fenced, True), (b'[]', True),
                     (json.dumps(VALUE).encode(), False), (b'[{}]', False),
                     (b'```json\n[}\n```', False), (fenced + b'\n[]', False),
                     (b'{}\n' + fenced, False), (fenced + b'\n' + fenced, False)]
            for index, (content, valid) in enumerate(cases):
                with self.subTest(index=index):
                    directory = root / f'array-{index}'
                    result = self.execute(root, plan, content, directory)
                    self.assertEqual(0 if valid else 1, result.returncode, result.stderr)
                    self.assertEqual(content, (directory / 'native.stdout').read_bytes())
                    self.assertEqual(b'native diagnostic\n', (directory / 'native.stderr').read_bytes())
                    diagnostic = json.loads((directory / 'diagnostic.json').read_text())
                    self.assertEqual(0, diagnostic['native_exit_code'])
                    self.assertEqual(result.returncode, diagnostic['exit_code'])
                    if valid:
                        self.assertEqual([] if content == b'[]' else [VALUE], json.loads(result.stdout))
                    else:
                        self.assertEqual(content, result.stdout)
                        self.assertEqual('invalid-output', diagnostic['code'])


if __name__ == "__main__":
    unittest.main()
