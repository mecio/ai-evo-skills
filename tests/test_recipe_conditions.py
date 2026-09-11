from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import shutil
import sys
import unittest

import yaml
import test_cli as fixtures
from ai_evo_skills.execution import ExecutionError, validate_plan
from ai_evo_skills.recipe_runtime import advance_recipe, skipped_output


class RecipeConditionsTest(unittest.TestCase):
    repository = fixtures.CliIntegrationTest.repository
    initialize = fixtures.CliIntegrationTest.initialize
    run_cli = fixtures.CliIntegrationTest.run_cli

    @contextmanager
    def project(self):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, 'codex', 'claude')
            commands = root / '.ai-evo-prj/skills/catalog/commands'
            for name in ('detect', 'legacy', 'unit', 'aggregate'):
                path = commands / f'abc-{name}/SKILL.md'
                path.parent.mkdir(parents=True)
                content = fixtures.VALID_COMMAND.replace('abc-inspect', f'abc-{name}')
                if name == 'aggregate':
                    content = content.replace('inputs: {}', 'inputs:\n  unit:\n    description: Unit result or skipped marker JSON\n    required: true')
                path.write_text(content)
            recipe = root / '.ai-evo-prj/skills/catalog/recipes/abc-recipe-flow'
            recipe.mkdir(parents=True)
            (recipe / 'SKILL.md').write_text(fixtures.VALID_FLOW_SKILL)
            data = {
                'version': '1.0', 'name': 'abc-recipe-flow', 'executor': 'current',
                'inputs': {'php': {'description': 'PHP context', 'default': 'php83'}},
                'steps': [{'id': 'detect', 'uses': 'abc-detect'},
                          {'id': 'legacy', 'uses': 'abc-legacy'},
                          {'id': 'unit', 'uses': 'abc-unit',
                           'when': {'value': '${{ steps.detect.output }}', 'equals': 'php83'}},
                          {'id': 'aggregate', 'uses': 'abc-aggregate',
                           'with': {'unit': '${{ steps.unit.output }}'}}],
                'outputs': {'result': {'value': '${{ steps.aggregate.output }}'}},
            }
            yield root, recipe / 'recipe.yaml', data

    def plan(self, root, path, data, adapter='codex', *inputs):
        path.write_text(yaml.safe_dump(data))
        result = self.run_cli(root, 'recipe', 'plan', 'abc-recipe-flow', '--adapter', adapter, *inputs)
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout)

    def result(self, sid, output):
        return {'step': sid, 'status': 'succeeded', 'output': output}

    def test_unconditional_plan_keeps_existing_shape_and_outputs(self):
        with self.project() as (root, path, data):
            del data['steps'][2]['when']
            plan = self.plan(root, path, data)
            self.assertNotIn('conditions', plan['execution'])
            self.assertTrue(all('when' not in step for step in plan['execution']['steps']))
            results = []
            for sid in ('detect', 'legacy', 'unit', 'aggregate'):
                transition = advance_recipe({'plan': plan, 'results': results})
                self.assertEqual('ready', transition['status'])
                self.assertEqual(sid, transition['step']['id'])
                validate_plan(transition['step'])
                results.append(self.result(sid, sid))
            self.assertEqual('aggregate', advance_recipe({'plan': plan, 'results': results})['output'])

    def test_input_condition_and_exact_comparison_for_both_adapters(self):
        with self.project() as (root, path, data):
            data['steps'][2]['when']['value'] = '${{ inputs.php }}'
            for adapter in ('codex', 'claude'):
                for value, expected in (('php83', 'ready'), ('php72', 'skipped'),
                                        ('php83\n', 'skipped'), (' php83', 'skipped'), ('PHP83', 'skipped')):
                    with self.subTest(adapter=adapter, value=value):
                        plan = self.plan(root, path, data, adapter, '--input', 'php=' + value)
                        step = plan['execution']['steps'][2]
                        self.assertEqual({'all': [{'value': value, 'equals': 'php83'}]}, step['when'])
                        self.assertEqual(adapter, step['application']['executor'])
                        transition = advance_recipe({'plan': plan, 'results': [self.result('detect', ''), self.result('legacy', '')]})
                        self.assertEqual(expected, transition['status'])

    def test_output_conditions_use_typed_references_and_preserve_json(self):
        with self.project() as (root, path, data):
            plan = self.plan(root, path, data)
            self.assertEqual(plan, json.loads(json.dumps(plan)))
            self.assertEqual('exact-equals-v1', plan['execution']['conditions'])
            step = plan['execution']['steps'][2]
            self.assertEqual({'type': 'ai-evo-step-output', 'step': 'detect'}, step['when']['all'][0]['value'])
            for value, status in (('php83', 'ready'), ('php72', 'skipped'), ('php83\n', 'skipped'), ('', 'skipped')):
                transition = advance_recipe({'plan': plan, 'results': [self.result('detect', value), self.result('legacy', '')]})
                self.assertEqual(status, transition['status'])
                if status == 'ready':
                    self.assertNotIn('when', transition['step'])
                    validate_plan(transition['step'])

    def test_trim_is_explicit_preserves_outputs_and_only_normalizes_value(self):
        with self.project() as (root, path, data):
            for source in ('${{ inputs.php }}', '${{ steps.detect.output }}'):
                for adapter in ('codex', 'claude'):
                    data['steps'][2]['when'] = {'value': source, 'normalize': 'trim', 'equals': 'php83'}
                    plan = self.plan(root, path, data, adapter, '--input', 'php= \tphp83\r\n')
                    self.assertEqual('trim', plan['execution']['steps'][2]['when']['all'][0]['normalize'])
                    for value, expected in (('php83', 'ready'), ('php83\n', 'ready'),
                                            (' \tphp83\r\n', 'ready'), ('\u00a0php83\u00a0', 'ready'),
                                            ('php 83', 'skipped'), ('PHP83', 'skipped'),
                                            ('Failure: php83', 'skipped'), ('php72\n', 'skipped'), (' \n', 'skipped')):
                        with self.subTest(source=source, adapter=adapter, value=value):
                            snapshot = deepcopy(plan)
                            if source.startswith('${{ inputs.'):
                                snapshot['execution']['steps'][2]['when']['all'][0]['value'] = value
                            records = [self.result('detect', value), self.result('legacy', '')]
                            before = deepcopy((snapshot, records))
                            transition = advance_recipe({'plan': snapshot, 'results': records})
                            self.assertEqual(expected, transition['status'])
                            self.assertEqual(before, (snapshot, records))
                    # The expected literal is not trimmed, and neither are downstream outputs.
                    plan['execution']['steps'][2]['when']['all'][0]['equals'] = ' php83 '
                    records = [self.result('detect', ' php83 '), self.result('legacy', '')]
                    self.assertEqual('skipped', advance_recipe({'plan': plan, 'results': records})['status'])
            data['steps'][3]['with']['unit'] = '${{ steps.detect.output }}'
            plan = self.plan(root, path, data)
            records = [self.result('detect', 'php83\n'), self.result('legacy', ''), self.result('unit', 'ok')]
            self.assertEqual('php83\n', advance_recipe({'plan': plan, 'results': records})['step']['with']['unit'])
            plan['result']['step'] = 'detect'
            records.append(self.result('aggregate', 'ok'))
            self.assertEqual('php83\n', advance_recipe({'plan': plan, 'results': records})['output'])

    def test_invalid_normalization_is_rejected_in_authoring_and_runtime(self):
        with self.project() as (root, path, data):
            valid_plan = self.plan(root, path, data)
            for normalize in ('lower', 'none', True, None, {}, ['trim']):
                with self.subTest(normalize=normalize):
                    data['steps'][2]['when']['normalize'] = normalize
                    path.write_text(yaml.safe_dump(data))
                    for args in (('validate',), ('recipe', 'plan', 'abc-recipe-flow', '--adapter', 'codex')):
                        result = self.run_cli(root, *args)
                        self.assertEqual(1, result.returncode)
                        self.assertIn('normalize', result.stderr)
                    snapshot = deepcopy(valid_plan)
                    snapshot['execution']['steps'][2]['when']['all'][0]['normalize'] = normalize
                    with self.assertRaises(ExecutionError):
                        advance_recipe({'plan': snapshot, 'results': []})

    def test_unknown_forward_self_and_cyclic_references_are_rejected(self):
        with self.project() as (root, path, data):
            for value in ('${{ inputs.missing }}', '${{ steps.missing.output }}',
                          '${{ steps.aggregate.output }}', '${{ steps.unit.output }}'):
                with self.subTest(value=value):
                    data['steps'][2]['when']['value'] = value
                    path.write_text(yaml.safe_dump(data))
                    for args in (('validate',), ('recipe', 'plan', 'abc-recipe-flow', '--adapter', 'codex')):
                        result = self.run_cli(root, *args)
                        self.assertEqual(1, result.returncode)
                        self.assertIn('when.value', result.stderr)
                        self.assertNotIn('Traceback', result.stderr)
            # The unit guard depends on aggregate, whose input depends on unit.
            data['steps'][2]['when']['value'] = '${{ steps.aggregate.output }}'
            path.write_text(yaml.safe_dump(data))
            result = self.run_cli(root, 'validate')
            self.assertEqual(1, result.returncode)

    def test_unsupported_condition_syntax_is_rejected(self):
        with self.project() as (root, path, data):
            for guard in ('php83', {}, {'value': '${{ inputs.php }}', 'not-equals': 'php72'},
                          {'value': 'prefix ${{ inputs.php }}', 'equals': 'php83'},
                          {'value': '${{ inputs.php }} suffix', 'equals': 'php83'},
                          {'value': 'php83', 'equals': 'php83'},
                          {'value': '${{ inputs.php }}', 'equals': 83},
                          {'value': '${{ inputs.php }}', 'equals': 'php83', 'extra': True}):
                with self.subTest(guard=guard):
                    data['steps'][2]['when'] = guard
                    path.write_text(yaml.safe_dump(data))
                    for args in (('validate',), ('recipe', 'plan', 'abc-recipe-flow', '--adapter', 'claude')):
                        result = self.run_cli(root, *args)
                        self.assertEqual(1, result.returncode)
                        self.assertIn('when', result.stderr)

    def test_skipped_outputs_can_be_aggregated_and_returned_as_final_state(self):
        with self.project() as (root, path, data):
            plan = self.plan(root, path, data)
            results = [self.result('detect', 'php72'), self.result('legacy', 'legacy ok')]
            skipped = advance_recipe({'plan': plan, 'results': results})
            self.assertEqual('skipped', skipped['status'])
            self.assertEqual(skipped_output('unit'), skipped['result']['output'])
            results.append(skipped['result'])
            aggregate = advance_recipe({'plan': plan, 'results': results})
            self.assertEqual('ready', aggregate['status'])
            self.assertEqual(skipped_output('unit'), json.loads(aggregate['step']['with']['unit']))
            validate_plan(aggregate['step'])
            results.append(self.result('aggregate', 'legacy passed; unit skipped'))
            self.assertEqual('legacy passed; unit skipped', advance_recipe({'plan': plan, 'results': results})['output'])
            plan['result']['step'] = 'unit'
            self.assertEqual(skipped_output('unit'), advance_recipe({'plan': plan, 'results': results})['output'])

    def test_condition_on_skipped_output_is_false_not_magic_string_equality(self):
        with self.project() as (root, path, data):
            data['steps'][3]['when'] = {'value': '${{ steps.unit.output }}', 'normalize': 'trim', 'equals': json.dumps(skipped_output('unit'))}
            plan = self.plan(root, path, data)
            results = [self.result('detect', 'php72'), self.result('legacy', '')]
            results.append(advance_recipe({'plan': plan, 'results': results})['result'])
            self.assertEqual('skipped', advance_recipe({'plan': plan, 'results': results})['status'])

    def test_missing_invalid_and_out_of_order_outputs_stop_runtime(self):
        with self.project() as (root, path, data):
            plan = self.plan(root, path, data)
            for records in ([self.result('legacy', '')], [{'step': 'detect', 'status': 'succeeded'}],
                            [self.result('detect', None)], [self.result('detect', {'bad': 'output'})],
                            [{'step': 'detect', 'status': 'skipped', 'output': skipped_output('detect')}],
                            [self.result('detect', 'php72'), self.result('legacy', ''), self.result('unit', 'ran')]):
                with self.subTest(records=records), self.assertRaises(ExecutionError):
                    advance_recipe({'plan': plan, 'results': records})
            broken = deepcopy(plan)
            broken['execution']['steps'][2]['when']['all'][0]['value']['step'] = 'absent'
            with self.assertRaises(ExecutionError):
                advance_recipe({'plan': broken, 'results': []})

    def test_false_condition_does_not_hide_disabled_executor_or_cycles(self):
        with self.project() as (root, path, data):
            data['steps'][2]['when'] = {'value': '${{ inputs.php }}', 'equals': 'never'}
            skill = root / '.ai-evo-prj/skills/catalog/commands/abc-unit/SKILL.md'
            skill.write_text(skill.read_text().replace('executor: current', 'executor: claude'))
            config_path = root / '.ai-evo-skills.yaml'
            config = yaml.safe_load(config_path.read_text())
            config['targets'][1]['enabled'] = False
            config_path.write_text(yaml.safe_dump(config))
            path.write_text(yaml.safe_dump(data))
            result = self.run_cli(root, 'recipe', 'plan', 'abc-recipe-flow', '--adapter', 'codex')
            self.assertEqual(1, result.returncode)
            self.assertIn('disabled adapter claude', result.stderr)
            data['steps'][2]['uses'] = 'abc-recipe-flow'
            path.write_text(yaml.safe_dump(data))
            result = self.run_cli(root, 'validate')
            self.assertEqual(1, result.returncode)
            self.assertIn('recipe cycle', result.stderr)

    def test_nested_recipe_conditions_gate_every_descendant(self):
        with self.project() as (root, path, data):
            nested = path.parent.parent / 'abc-recipe-nested'
            nested.mkdir()
            (nested / 'SKILL.md').write_text(fixtures.VALID_FLOW_SKILL.replace('abc-recipe-flow', 'abc-recipe-nested'))
            (nested / 'recipe.yaml').write_text(yaml.safe_dump({
                'version': '1.0', 'name': 'abc-recipe-nested', 'executor': 'current', 'inputs': {},
                'steps': [{'id': 'first', 'uses': 'abc-unit'},
                          {'id': 'second', 'uses': 'abc-unit', 'when': {'value': '${{ steps.first.output }}', 'equals': 'go'}}],
                'outputs': {'result': {'value': '${{ steps.second.output }}'}},
            }))
            data['steps'][2]['uses'] = 'abc-recipe-nested'
            data['steps'][2]['when']['normalize'] = 'trim'
            plan = self.plan(root, path, data)
            self.assertEqual(['detect', 'legacy', 'unit.first', 'unit.second', 'aggregate'], [s['id'] for s in plan['execution']['steps']])
            self.assertEqual(2, len(plan['execution']['steps'][3]['when']['all']))
            for context, child_output, statuses in (('php72', '', ['skipped', 'skipped']),
                                                     ('php83', 'go', ['ready', 'ready']),
                                                     ('php83', 'stop', ['ready', 'skipped']),
                                                     ('php83\n', 'go', ['ready', 'ready']),
                                                     ('php83\n', 'go\n', ['ready', 'skipped'])):
                records = [self.result('detect', context), self.result('legacy', '')]
                for sid, status in zip(('unit.first', 'unit.second'), statuses):
                    transition = advance_recipe({'plan': plan, 'results': records})
                    self.assertEqual(status, transition['status'])
                    records.append(transition['result'] if status == 'skipped' else self.result(sid, child_output))
                self.assertEqual('ready', advance_recipe({'plan': plan, 'results': records})['status'])

    def test_cli_coordinator_skips_without_spawning_and_enforces_fail_fast(self):
        with self.project() as (root, path, data):
            for context, failure in (('php72', False), ('php83', False), ('php83', True)):
                with self.subTest(context=context, failure=failure):
                    plan = self.plan(root, path, data)
                    for step in plan['execution']['steps']:
                        code = ('import json,sys; from pathlib import Path; p=json.load(sys.stdin)["plan"]; '
                                'Path(p["id"]+".ran").write_text("yes"); '
                                'sys.stdout.write(' + repr(context if step['id'] == 'detect' else step['id']) + '); '
                                'sys.exit(' + ('17' if failure and step['id'] == 'legacy' else '0') + ')')
                        step['application']['command'] = [sys.executable, '-c', code]
                    records = []
                    for _ in range(6):
                        response = subprocess.run(fixtures.COMMAND + ['recipe', 'advance'], cwd=root,
                                                  env=fixtures.CLI_ENV, input=json.dumps({'plan': plan, 'results': records}),
                                                  text=True, capture_output=True)
                        transition = json.loads(response.stdout)
                        if transition['status'] in ('complete', 'failed'):
                            self.assertEqual('failed' if failure else 'complete', transition['status'])
                            self.assertEqual(1 if failure else 0, response.returncode)
                            break
                        self.assertEqual(0, response.returncode, response.stderr)
                        if transition['status'] == 'skipped':
                            records.append(transition['result'])
                            continue
                        step = transition['step']
                        executed = subprocess.run(fixtures.COMMAND + ['command', 'execute'], cwd=root,
                                                  env=fixtures.CLI_ENV, input=json.dumps(step), text=True, capture_output=True)
                        records.append({'step': step['id'], 'status': 'failed', 'exit_code': executed.returncode}
                                       if executed.returncode else self.result(step['id'], executed.stdout))
                    else:
                        self.fail('recipe did not terminate')
                    self.assertEqual(context == 'php83' and not failure, (root / 'unit.ran').exists())
                    self.assertEqual(not failure, (root / 'aggregate.ran').exists())
                    for marker in root.glob('*.ran'):
                        marker.unlink()

    def test_command_execute_rejects_unresolved_conditional_steps(self):
        with self.project() as (root, path, data):
            plan = self.plan(root, path, data)
            step = plan['execution']['steps'][2]
            step['application']['command'] = [sys.executable, '-c', 'raise SystemExit(99)']
            result = subprocess.run(fixtures.COMMAND + ['command', 'execute'], cwd=root, env=fixtures.CLI_ENV,
                                    input=json.dumps(step), text=True, capture_output=True)
            self.assertEqual(1, result.returncode)
            self.assertIn('when', result.stderr)

    def test_skip_allows_an_independent_current_mode_step(self):
        with self.project() as (root, path, data):
            skill = root / '.ai-evo-prj/skills/catalog/commands/abc-legacy/SKILL.md'
            skill.write_text(skill.read_text().replace('workspace: read-only', 'workspace: read-write').replace('network: disabled', 'network: auto'))
            data['steps'].insert(3, {'id': 'independent', 'uses': 'abc-legacy'})
            plan = self.plan(root, path, data)
            records = [self.result('detect', 'php72'), self.result('legacy', '')]
            records.append(advance_recipe({'plan': plan, 'results': records})['result'])
            transition = advance_recipe({'plan': plan, 'results': records})
            self.assertEqual('ready', transition['status'])
            self.assertEqual('independent', transition['step']['id'])
            self.assertEqual('current', transition['step']['application']['mode'])
            self.assertEqual({}, transition['step']['with'])

    def test_runtime_rejects_capability_mismatch_and_results_after_failure(self):
        with self.project() as (root, path, data):
            plan = self.plan(root, path, data)
            failed = {'step': 'legacy', 'status': 'failed', 'exit_code': 17}
            records = [self.result('detect', 'php83'), failed]
            self.assertEqual('failed', advance_recipe({'plan': plan, 'results': records})['status'])
            with self.assertRaisesRegex(ExecutionError, 'fail-fast'):
                advance_recipe({'plan': plan, 'results': records + [self.result('unit', 'must not run')]})
            del plan['execution']['conditions']
            with self.assertRaisesRegex(ExecutionError, 'capability'):
                advance_recipe({'plan': plan, 'results': []})

    def test_acme_example_validates_and_runs_both_branches_for_both_coordinators(self):
        temporary, root = self.repository()
        with temporary:
            initialized = self.run_cli(root, 'init', '--namespace', 'acme', '--adapter', 'codex', '--adapter', 'claude')
            self.assertEqual(0, initialized.returncode, initialized.stderr)
            shutil.copytree(fixtures.ENGINE / 'examples/acme/catalog',
                            root / '.ai-evo-prj/skills/catalog', dirs_exist_ok=True)
            checked = self.run_cli(root, 'validate')
            self.assertEqual(0, checked.returncode, checked.stderr)
            for adapter in ('codex', 'claude'):
                planned = self.run_cli(root, 'recipe', 'plan', 'acme-recipe-review-security-if-changed', '--adapter', adapter)
                self.assertEqual(0, planned.returncode, planned.stderr)
                plan = json.loads(planned.stdout)
                for context in ('clean', 'changed'):
                    results, executed = [], []
                    while True:
                        transition = advance_recipe({'plan': plan, 'results': results})
                        if transition['status'] == 'complete':
                            self.assertEqual('report', transition['output'])
                            break
                        if transition['status'] == 'skipped':
                            results.append(transition['result'])
                            continue
                        step = transition['step']
                        executed.append(step['id'])
                        if step['id'] in ('review', 'report'):
                            self.assertEqual('security', step['with']['focus'])
                        if step['id'] == 'report':
                            if context == 'clean':
                                self.assertEqual(skipped_output('review'), json.loads(step['with']['review']))
                            else:
                                self.assertEqual('review', step['with']['review'])
                        validate_plan(step)
                        step['application']['command'] = [sys.executable, '-c', 'import sys; sys.stdout.write(' + repr(context + '\n' if step['id'] == 'detect' else step['id']) + ')']
                        result = subprocess.run(fixtures.COMMAND + ['command', 'execute'], cwd=root,
                                                env=fixtures.CLI_ENV, input=json.dumps(step), text=True, capture_output=True)
                        self.assertEqual(0, result.returncode, result.stderr)
                        results.append(self.result(step['id'], result.stdout))
                    self.assertEqual(['detect'] + (['review'] if context == 'changed' else []) + ['report'], executed)
