from contextlib import contextmanager
from copy import deepcopy
import json
import unittest

import yaml

import test_cli as fixtures
from ai_evo_skills.execution import ExecutionError, validate_plan
from ai_evo_skills.recipe_runtime import advance_recipe


class RecipeForEachTest(unittest.TestCase):
    repository = fixtures.CliIntegrationTest.repository
    initialize = fixtures.CliIntegrationTest.initialize
    run_cli = fixtures.CliIntegrationTest.run_cli

    @contextmanager
    def project(self):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, 'codex')
            commands = root / '.ai-evo-prj/skills/catalog/commands'
            for name, inputs in (
                ('produce', {}),
                ('apply', {'value': {'description': 'Current item', 'required': True}}),
                ('collect', {'values': {'description': 'Iteration outputs', 'required': True}}),
            ):
                path = commands / f'abc-{name}/SKILL.md'
                path.parent.mkdir(parents=True)
                body = fixtures.VALID_COMMAND.replace('abc-inspect', f'abc-{name}')
                body = body.replace('inputs: {}', yaml.safe_dump({'inputs': inputs}, sort_keys=False).strip())
                path.write_text(body)

            recipes = root / '.ai-evo-prj/skills/catalog/recipes'
            child = recipes / '_iterations/abc-recipe-item'
            child.mkdir(parents=True)
            (child / 'SKILL.md').write_text(
                fixtures.VALID_FLOW_SKILL.replace('abc-recipe-flow', 'abc-recipe-item')
            )
            (child / 'recipe.yaml').write_text(yaml.safe_dump({
                'version': '1.0', 'name': 'abc-recipe-item',
                'inputs': {'item': {'description': 'Current item', 'required': True}},
                'steps': [{'id': 'apply', 'uses': 'abc-apply',
                           'with': {'value': '${{ inputs.item }}'}}],
                'outputs': {'result': {'value': '${{ steps.apply.output }}'}},
            }, sort_keys=False))

            parent = recipes / 'abc-recipe-flow'
            parent.mkdir(parents=True)
            (parent / 'SKILL.md').write_text(fixtures.VALID_FLOW_SKILL)
            data = {
                'version': '1.0', 'name': 'abc-recipe-flow', 'inputs': {},
                'steps': [
                    {'id': 'produce', 'uses': 'abc-produce'},
                    {'id': 'items', 'uses': 'abc-recipe-item',
                     'for_each': {'items': '${{ steps.produce.output }}'},
                     'with': {'item': '${{ item }}'}},
                    {'id': 'collect', 'uses': 'abc-collect',
                     'with': {'values': '${{ steps.items.output }}'}},
                ],
                'outputs': {'result': {'value': '${{ steps.collect.output }}'}},
            }
            yield root, parent / 'recipe.yaml', data

    def plan(self, root, path, data):
        path.write_text(yaml.safe_dump(data, sort_keys=False))
        result = self.run_cli(root, 'recipe', 'plan', 'abc-recipe-flow', '--adapter', 'codex')
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout)

    @staticmethod
    def result(step, output, status='succeeded'):
        return {'step': step, 'status': status, 'output': output}

    def test_plan_and_runtime_iterate_sequentially_and_collect_outputs(self):
        with self.project() as (root, path, data):
            plan = self.plan(root, path, data)
            self.assertEqual('json-array-sequential-v1', plan['execution']['iterations'])
            self.assertEqual(['produce', 'items', 'collect'],
                             [node['id'] for node in plan['execution']['steps']])
            loop = plan['execution']['steps'][1]
            self.assertEqual('items.apply', loop['steps'][0]['id'])
            self.assertEqual({'type': 'ai-evo-foreach-item'}, loop['steps'][0]['with']['value'])

            records = []
            transition = advance_recipe({'plan': plan, 'results': records})
            self.assertEqual('produce', transition['step']['id'])
            records.append(self.result('produce', '["alpha", {"sequence": 1}]'))

            transition = advance_recipe({'plan': plan, 'results': records})
            self.assertEqual('items.0.apply', transition['step']['id'])
            self.assertEqual('alpha', transition['step']['with']['value'])
            validate_plan(transition['step'])
            records.append(self.result('items.0.apply', 'done-alpha'))

            transition = advance_recipe({'plan': plan, 'results': records})
            self.assertEqual('items.1.apply', transition['step']['id'])
            self.assertEqual('{"sequence":1}', transition['step']['with']['value'])
            validate_plan(transition['step'])
            records.append(self.result('items.1.apply', 'done-object'))

            transition = advance_recipe({'plan': plan, 'results': records})
            self.assertEqual('collect', transition['step']['id'])
            self.assertEqual('["done-alpha","done-object"]', transition['step']['with']['values'])
            records.append(self.result('collect', 'complete'))
            self.assertEqual('complete', advance_recipe({'plan': plan, 'results': records})['output'])

    def test_iteration_recipe_is_nested_only_and_not_published(self):
        with self.project() as (root, path, data):
            path.write_text(yaml.safe_dump(data, sort_keys=False))
            direct = self.run_cli(
                root, 'recipe', 'plan', 'abc-recipe-item', '--adapter', 'codex',
                '--input', 'item=value'
            )
            self.assertEqual(1, direct.returncode)
            self.assertIn('unknown recipe abc-recipe-item', direct.stderr)

            synced = self.run_cli(root, 'sync')
            self.assertEqual(0, synced.returncode, synced.stderr)
            self.assertFalse((root / '.agents/skills/abc-recipe-item').exists())
            self.assertTrue((root / '.agents/skills/abc-recipe-flow').is_symlink())

    def test_empty_array_skips_loop_and_invalid_items_fail(self):
        with self.project() as (root, path, data):
            plan = self.plan(root, path, data)
            records = [self.result('produce', '[]')]
            transition = advance_recipe({'plan': plan, 'results': records})
            self.assertEqual('collect', transition['step']['id'])
            self.assertEqual('[]', transition['step']['with']['values'])
            for output in ('{}', 'null', '"text"', 'broken'):
                with self.subTest(output=output), self.assertRaises(ExecutionError):
                    advance_recipe({'plan': plan, 'results': [self.result('produce', output)]})

    def test_failed_iteration_is_fail_fast_and_resume_is_stable(self):
        with self.project() as (root, path, data):
            plan = self.plan(root, path, data)
            records = [self.result('produce', '["a","b"]'), self.result('items.0.apply', 'a')]
            first = advance_recipe({'plan': plan, 'results': records})
            second = advance_recipe({'plan': deepcopy(plan), 'results': deepcopy(records)})
            self.assertEqual(first, second)
            failed = {'step': 'items.1.apply', 'status': 'failed', 'exit_code': 17}
            self.assertEqual('failed', advance_recipe({'plan': plan, 'results': records + [failed]})['status'])
            with self.assertRaises(ExecutionError):
                advance_recipe({'plan': plan, 'results': records + [failed, self.result('collect', 'bad')]})

    def test_authoring_rejects_invalid_foreach_uses(self):
        with self.project() as (root, path, data):
            invalid = []
            command_loop = deepcopy(data)
            command_loop['steps'][1]['uses'] = 'abc-apply'
            invalid.append((command_loop, 'for_each may only invoke a recipe'))
            guarded = deepcopy(data)
            guarded['steps'][1]['when'] = {'value': '${{ steps.produce.output }}', 'equals': '[]'}
            invalid.append((guarded, 'for_each and when cannot be combined'))
            outside = deepcopy(data)
            outside['steps'][2]['with']['values'] = '${{ item }}'
            invalid.append((outside, 'item is only available'))
            forward = deepcopy(data)
            forward['steps'][1]['for_each']['items'] = '${{ steps.collect.output }}'
            invalid.append((forward, 'must reference a previous step'))
            for recipe, message in invalid:
                with self.subTest(message=message):
                    path.write_text(yaml.safe_dump(recipe, sort_keys=False))
                    result = self.run_cli(root, 'validate')
                    self.assertEqual(1, result.returncode)
                    self.assertIn(message, result.stderr)

    def test_nested_foreach_is_rejected_during_planning(self):
        with self.project() as (root, path, data):
            path.write_text(yaml.safe_dump(data, sort_keys=False))
            child_path = path.parent.parent / '_iterations/abc-recipe-item/recipe.yaml'
            child = yaml.safe_load(child_path.read_text())
            child['steps'][0] = {
                'id': 'nested', 'uses': 'abc-recipe-leaf',
                'for_each': {'items': '${{ inputs.item }}'},
                'with': {'item': '${{ item }}'},
            }
            child['outputs']['result']['value'] = '${{ steps.nested.output }}'
            leaf = path.parent.parent / 'abc-recipe-leaf'
            leaf.mkdir()
            (leaf / 'SKILL.md').write_text(
                fixtures.VALID_FLOW_SKILL.replace('abc-recipe-flow', 'abc-recipe-leaf')
            )
            (leaf / 'recipe.yaml').write_text(yaml.safe_dump({
                'version': '1.0', 'name': 'abc-recipe-leaf',
                'inputs': {'item': {'description': 'Current item', 'required': True}},
                'steps': [{'id': 'apply', 'uses': 'abc-apply',
                           'with': {'value': '${{ inputs.item }}'}}],
                'outputs': {'result': {'value': '${{ steps.apply.output }}'}},
            }, sort_keys=False))
            child_path.write_text(yaml.safe_dump(child, sort_keys=False))
            validation = self.run_cli(root, 'validate')
            self.assertEqual(1, validation.returncode)
            self.assertIn('nested for_each is not supported', validation.stderr)
            result = self.run_cli(root, 'recipe', 'plan', 'abc-recipe-flow', '--adapter', 'codex')
            self.assertEqual(1, result.returncode)
            self.assertIn('nested for_each is not supported', result.stderr)


if __name__ == '__main__':
    unittest.main()
