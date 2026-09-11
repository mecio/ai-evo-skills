from contextlib import contextmanager
import json
import unittest

import yaml
import test_cli as fixtures


class InputContractTest(unittest.TestCase):
    repository = fixtures.CliIntegrationTest.repository
    initialize = fixtures.CliIntegrationTest.initialize
    run_cli = fixtures.CliIntegrationTest.run_cli

    @contextmanager
    def project(self):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, 'codex')
            command = root / '.ai-evo-prj/skills/catalog/commands/abc-inspect/SKILL.md'
            command.parent.mkdir(parents=True)
            recipe = root / '.ai-evo-prj/skills/catalog/recipes/abc-recipe-flow'
            recipe.mkdir(parents=True)
            (recipe / 'SKILL.md').write_text(fixtures.VALID_FLOW_SKILL)
            data = {
                'version': '1.0', 'name': 'abc-recipe-flow', 'executor': 'current',
                'inputs': {'target': {'description': 'Target', 'default': 'main'}},
                'steps': [{'id': 'first', 'uses': 'abc-inspect', 'with': {'value': 'initial'}},
                          {'id': 'second', 'uses': 'abc-inspect',
                           'with': {'value': '${{ steps.first.output }}'}}],
                'outputs': {'result': {'value': '${{ steps.second.output }}'}},
            }
            path = recipe / 'recipe.yaml'
            path.write_text(yaml.safe_dump(data))
            self.write_command(command, {'default': 'fallback'})
            yield root, command, path, data

    def write_command(self, path, spec):
        inputs = yaml.safe_dump({'inputs': {'value': {'description': 'Value', **spec}}}).rstrip()
        path.write_text(fixtures.VALID_COMMAND.replace('inputs: {}', inputs))

    def assert_rejected(self, root, message):
        for arguments in (('validate',), ('sync', '--dry-run'),
                          ('command', 'plan', 'abc-inspect', '--adapter', 'codex'),
                          ('recipe', 'plan', 'abc-recipe-flow', '--adapter', 'codex')):
            with self.subTest(arguments=arguments):
                result = self.run_cli(root, *arguments)
                self.assertEqual(1, result.returncode, result.stdout)
                self.assertIn(message, result.stderr)
                self.assertNotIn('Traceback', result.stderr)
                self.assertEqual('', result.stdout)

    def test_invalid_required_cannot_be_hidden_by_default(self):
        with self.project() as (root, command, _, _):
            for value in ('true', False, None, 1, [], {}):
                with self.subTest(required=value):
                    self.write_command(command, {'required': value, 'default': 'fallback'})
                    self.assert_rejected(root, 'required must be the boolean true')

    def test_command_inputs_require_exactly_one_presence_marker(self):
        with self.project() as (root, command, _, _):
            for spec in ({}, {'required': True, 'default': 'fallback'}):
                with self.subTest(spec=spec):
                    self.write_command(command, spec)
                    self.assert_rejected(root, 'declare exactly one')
            self.write_command(command, {'default': 1})
            self.assert_rejected(root, 'default must be a string')

    def test_partial_references_are_rejected_in_every_position(self):
        with self.project() as (root, _, path, data):
            for value in ('prefix ${{ steps.first.output }}',
                          '${{ steps.first.output }} suffix',
                          'prefix ${{ inputs.target }} suffix',
                          'prefix ${{ steps.missing.output }}',
                          'prefix ${{ inputs.missing }}',
                          'prefix ${{ steps.first.output',
                          '${{ steps.first.output }} ${{ inputs.target }}'):
                with self.subTest(value=value):
                    data['steps'][1]['with']['value'] = value
                    path.write_text(yaml.safe_dump(data))
                    self.assert_rejected(root, 'invalid variable expression')

    def test_valid_inputs_literals_and_complete_references_keep_their_values(self):
        with self.project() as (root, command, path, data):
            self.write_command(command, {'required': True})
            result = self.run_cli(root, 'command', 'plan', 'abc-inspect', '--adapter', 'codex')
            self.assertEqual(1, result.returncode)
            self.assertIn('missing required input value', result.stderr)
            result = self.run_cli(root, 'command', 'plan', 'abc-inspect', '--adapter', 'codex',
                                  '--input', 'value=')
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual({'value': ''}, json.loads(result.stdout)['with'])
            self.write_command(command, {'default': ''})
            result = self.run_cli(root, 'command', 'plan', 'abc-inspect', '--adapter', 'codex')
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual({'value': ''}, json.loads(result.stdout)['with'])
            for value, expected in (
                ('${{ inputs.target }}', 'main'),
                ('${{ steps.first.output }}', {'type': 'ai-evo-step-output', 'step': 'first'}),
                ('', ''), ('literal $HOME {braces}', 'literal $HOME {braces}'),
            ):
                with self.subTest(value=value):
                    data['steps'][1]['with']['value'] = value
                    path.write_text(yaml.safe_dump(data))
                    result = self.run_cli(root, 'recipe', 'plan', 'abc-recipe-flow', '--adapter', 'codex')
                    self.assertEqual(0, result.returncode, result.stderr)
                    self.assertEqual({'value': expected}, json.loads(result.stdout)['execution']['steps'][1]['with'])
