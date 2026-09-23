"""Executor defaults, per-call overrides and nested recipe execution scopes."""
from contextlib import contextmanager
import json
import unittest

import yaml

import test_cli as fixtures
from ai_evo_skills.execution import validate_plan
from ai_evo_skills.recipe_runtime import advance_recipe


class StepExecutorTest(unittest.TestCase):
    repository = fixtures.CliIntegrationTest.repository
    initialize = fixtures.CliIntegrationTest.initialize
    run_cli = fixtures.CliIntegrationTest.run_cli

    @contextmanager
    def project(self, *adapters):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, *(adapters or ('codex', 'claude')))
            command = root / '.ai-evo-prj/skills/catalog/commands/abc-inspect/SKILL.md'
            command.parent.mkdir(parents=True)
            command.write_text(fixtures.VALID_COMMAND)
            yield root, command

    def recipe(self, root, name, steps, **fields):
        path = root / '.ai-evo-prj/skills/catalog/recipes' / name
        path.mkdir(exist_ok=True)
        (path / 'SKILL.md').write_text(fixtures.VALID_FLOW_SKILL.replace('abc-recipe-flow', name))
        (path / 'recipe.yaml').write_text(yaml.safe_dump({
            'version': '1.0', 'name': name, 'inputs': {}, 'steps': steps,
            'outputs': {'result': {'value': '${{ steps.' + steps[-1]['id'] + '.output }}'}},
            **fields,
        }))

    def plan(self, root, adapter='codex', name='abc-recipe-flow'):
        result = self.run_cli(root, 'recipe', 'plan', name, '--adapter', adapter)
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout)

    def test_commands_and_recipes_use_invoking_ai_and_publish_to_both_adapters(self):
        with self.project() as (root, command):
            command.write_text(command.read_text().replace('read-only', 'read-write').replace('disabled', 'auto'))
            self.recipe(root, 'abc-recipe-flow', [
                {'id': 'inspect', 'uses': 'abc-inspect'},
                {'id': 'explicit_current', 'uses': 'abc-inspect', 'executor': 'current'},
            ])
            result = self.run_cli(root, 'sync')
            self.assertEqual(0, result.returncode, result.stderr)
            for adapter, directory in (('codex', '.agents'), ('claude', '.claude')):
                for name in ('abc-inspect', 'abc-recipe-flow'):
                    self.assertTrue((root / directory / 'skills' / name).is_symlink())
                direct = self.run_cli(root, 'command', 'plan', 'abc-inspect', '--adapter', adapter)
                self.assertEqual(0, direct.returncode, direct.stderr)
                plan = self.plan(root, adapter)
                self.assertEqual(adapter, plan['profile']['adapter'])
                applications = [json.loads(direct.stdout)['application'],
                                *(step['application'] for step in plan['execution']['steps'])]
                for application in applications:
                    self.assertEqual(adapter, application['executor'])
                    self.assertEqual('current', application['mode'])

    def test_same_command_can_use_different_executors_without_changing_direct_invocation(self):
        with self.project() as (root, command):
            self.recipe(root, 'abc-recipe-flow', [
                {'id': 'review', 'uses': 'abc-inspect', 'executor': 'claude'},
                {'id': 'verify', 'uses': 'abc-inspect', 'executor': 'codex'},
                {'id': 'local', 'uses': 'abc-inspect'},
            ])
            for adapter in ('codex', 'claude'):
                plan = self.plan(root, adapter)
                self.assertEqual(adapter, plan['profile']['adapter'])
                self.assertEqual(['claude', 'codex', adapter],
                                 [step['application']['executor'] for step in plan['execution']['steps']])
                results = []
                for step in plan['execution']['steps']:
                    transition = advance_recipe({'plan': plan, 'results': results})
                    self.assertEqual('ready', transition['status'])
                    app = transition['step']['application']
                    self.assertEqual({'workspace': 'read-only', 'network': 'disabled'}, app['execution_policy'])
                    self.assertEqual(app['executor'], app['profile']['adapter'])
                    self.assertEqual('current' if step['id'] == 'local' else 'delegated', app['mode'])
                    if app['mode'] == 'delegated':
                        validate_plan(transition['step'])
                    if app['executor'] == 'codex':
                        self.assertEqual('read-only', app['cli_arguments'][app['cli_arguments'].index('--sandbox') + 1])
                        self.assertIn('sandbox_workspace_write.network_access=false', app['cli_arguments'])
                    else:
                        self.assertTrue(app['policy_instructions'])
                    results.append({'step': step['id'], 'status': 'succeeded', 'output': step['id'] + '\n'})
                self.assertEqual('local\n', advance_recipe({'plan': plan, 'results': results})['output'])
                direct = self.run_cli(root, 'command', 'plan', 'abc-inspect', '--adapter', adapter)
                self.assertEqual(adapter, json.loads(direct.stdout)['application']['executor'])
            self.assertNotIn('executor:', command.read_text())

    def test_explicit_step_executor_delegates_even_without_restrictive_policy(self):
        with self.project() as (root, command):
            command.write_text(command.read_text().replace('read-only', 'read-write').replace('disabled', 'auto'))
            self.recipe(root, 'abc-recipe-flow', [{'id': 'run', 'uses': 'abc-inspect', 'executor': 'claude'}])
            for adapter in ('codex', 'claude'):
                step = self.plan(root, adapter)['execution']['steps'][0]
                self.assertEqual('claude', step['application']['executor'])
                self.assertEqual('delegated', step['application']['mode'])
                validate_plan(step)

    def test_current_steps_keep_interactive_execution_with_policy_and_output_contract(self):
        with self.project() as (root, command):
            references = command.parent / 'references'
            references.mkdir()
            (references / 'result.json').write_text('{"type": "object"}')
            command.write_text(command.read_text().replace(
                'inputs: {}', 'output-schema: references/result.json\ninputs: {}'))
            self.recipe(root, 'abc-recipe-flow', [
                {'id': 'worklog_record', 'uses': 'abc-inspect', 'executor': 'current'},
            ])
            for adapter in ('codex', 'claude'):
                direct = json.loads(self.run_cli(root, 'command', 'plan', 'abc-inspect', '--adapter', adapter).stdout)
                step = self.plan(root, adapter)['execution']['steps'][0]
                for application in (direct['application'], step['application']):
                    self.assertEqual('current', application['mode'])
                    self.assertEqual({'workspace': 'read-only', 'network': 'disabled'}, application['execution_policy'])
                    self.assertIn('output_contract', application)
                    self.assertNotIn('-p', application['command'])

    def test_command_executor_is_rejected_including_explicit_current(self):
        with self.project() as (root, command):
            self.recipe(root, 'abc-recipe-flow', [{'id': 'run', 'uses': 'abc-inspect', 'executor': 'claude'}])
            for executor in ('current', 'codex', 'claude'):
                with self.subTest(executor=executor):
                    command.write_text(fixtures.VALID_COMMAND.replace(
                        'execution-policy:', f'executor: {executor}\nexecution-policy:'))
                    for args in (('validate',), ('sync',),
                                 ('command', 'plan', 'abc-inspect', '--adapter', 'codex'),
                                 ('recipe', 'plan', 'abc-recipe-flow', '--adapter', 'codex')):
                        result = self.run_cli(root, *args)
                        self.assertEqual(1, result.returncode)
                        self.assertIn('commands always use the current AI', result.stderr)
                        self.assertNotIn('Traceback', result.stderr)
                    self.assertFalse((root / '.agents/skills').exists())

    def test_nested_overrides_are_inherited_without_leaking_to_siblings(self):
        with self.project() as (root, command):
            command.write_text(command.read_text().replace('read-only', 'read-write').replace('disabled', 'auto'))
            self.recipe(root, 'abc-recipe-leaf', [{'id': 'run', 'uses': 'abc-inspect'}])
            self.recipe(root, 'abc-recipe-inner', [
                {'id': 'inherited', 'uses': 'abc-recipe-leaf'},
                {'id': 'current', 'uses': 'abc-inspect', 'executor': 'current'},
                {'id': 'codex', 'uses': 'abc-recipe-leaf', 'executor': 'codex'},
                {'id': 'after', 'uses': 'abc-inspect'},
            ])
            self.recipe(root, 'abc-recipe-flow', [
                {'id': 'nested', 'uses': 'abc-recipe-inner', 'executor': 'claude'},
                {'id': 'sibling', 'uses': 'abc-recipe-leaf'},
            ])
            for adapter in ('codex', 'claude'):
                steps = self.plan(root, adapter)['execution']['steps']
                self.assertEqual(['claude', 'claude', 'codex', 'claude', adapter],
                                 [s['application']['executor'] for s in steps])
                self.assertEqual(['delegated'] * 4 + ['current'], [s['application']['mode'] for s in steps])
                self.assertEqual('nested.inherited.run', steps[0]['id'])
                for step in steps[:-1]:
                    validate_plan(step)

    def test_recipe_executor_is_rejected_including_explicit_current(self):
        with self.project() as (root, _):
            for executor in ('current', 'codex', 'claude', None):
                with self.subTest(executor=executor):
                    self.recipe(root, 'abc-recipe-flow', [{'id': 'run', 'uses': 'abc-inspect'}], executor=executor)
                    for args in (('validate',), ('sync',),
                                 ('recipe', 'plan', 'abc-recipe-flow', '--adapter', 'codex')):
                        result = self.run_cli(root, *args)
                        self.assertEqual(1, result.returncode)
                        self.assertIn('recipes always use the current AI', result.stderr)
                        self.assertNotIn('Traceback', result.stderr)
                    self.assertFalse((root / '.agents/skills').exists())

    def test_disabled_unknown_and_malformed_step_executors_fail_before_publication(self):
        with self.project('codex') as (root, _):
            self.recipe(root, 'abc-recipe-inner', [{'id': 'run', 'uses': 'abc-inspect'}])
            for used in ('abc-inspect', 'abc-recipe-inner'):
                for executor in ('claude', 'missing', '', None, True, [], '${{ inputs.executor }}'):
                    with self.subTest(used=used, executor=executor):
                        self.recipe(root, 'abc-recipe-flow', [{
                            'id': 'run', 'uses': used, 'executor': executor,
                            'when': {'value': '${{ inputs.guard }}', 'equals': 'yes'},
                        }], inputs={'guard': {'description': 'Guard', 'default': 'no'}})
                        for args in (('validate',), ('sync',),
                                     ('recipe', 'plan', 'abc-recipe-flow', '--adapter', 'codex')):
                            result = self.run_cli(root, *args)
                            self.assertNotEqual(0, result.returncode)
                            self.assertNotIn('Traceback', result.stderr)
                            if executor == 'claude':
                                self.assertIn('requires disabled adapter claude', result.stderr)
                            elif executor == 'missing':
                                self.assertIn('unknown executor adapter missing', result.stderr)
                        self.assertFalse((root / '.agents/skills').exists())

    def test_command_interface_rejects_unsupported_fields(self):
        with self.project() as (root, command):
            valid = command.read_text()
            for replacement in ('executor: null\nexecution-policy:',
                                'unexpected: true\nexecution-policy:',
                                'executor: []\nexecution-policy:'):
                command.write_text(valid.replace('execution-policy:', replacement))
                result = self.run_cli(root, 'validate')
                self.assertNotEqual(0, result.returncode)
                self.assertNotIn('Traceback', result.stderr)


if __name__ == '__main__':
    unittest.main()
