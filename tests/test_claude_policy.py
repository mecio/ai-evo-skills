import itertools
import json
import shutil
import unittest

import yaml
import test_cli as fixtures
from ai_evo_skills.claude_policy import ClaudePolicyError, normalize_claude_arguments
from ai_evo_skills.execution import validate_plan


GIT_RULE = 'Bash(.ai-evo/bin/ai-evo-git-read *)'


def options(arguments):
    result = {}
    index = 0
    while index < len(arguments):
        key = arguments[index]
        index += 1
        if '=' in key:
            key, value = key.split('=', 1)
        elif key in ('-p', '--strict-mcp-config'):
            value = True
        else:
            value = arguments[index]
            index += 1
        if key in result:
            raise AssertionError(f'duplicate option: {key}')
        result[key] = value
    return result


class ClaudePolicyTest(unittest.TestCase):
    def test_all_layer_orders_produce_one_restrictive_policy(self):
        adapter = yaml.safe_load((fixtures.ENGINE / 'adapters/claude.yaml').read_text())
        layers = [
            ['--disallowedTools', 'Agent,WebSearch,WebFetch'],
            adapter['execution-policy-translation']['workspace-read-only']['cli-arguments'],
            adapter['execution-policy-translation']['network-disabled']['cli-arguments'],
        ]
        expected = {
            '--permission-mode': 'dontAsk', '--permission-prompts': 'none',
            '--tools': 'Bash,Glob,Grep,Read',
            '--allowedTools': GIT_RULE + ',Glob,Grep,Read',
            '--disallowedTools': 'Agent,Edit,NotebookEdit,WebFetch,WebSearch,Write',
            '--strict-mcp-config': True,
        }
        baseline = normalize_claude_arguments(*layers)
        for permutation in itertools.permutations(layers):
            actual = normalize_claude_arguments(*permutation)
            self.assertEqual(baseline, actual)
            self.assertEqual(expected, options(actual))
            self.assertEqual(actual, normalize_claude_arguments(actual))

    def test_scoped_grants_are_not_widened_and_deny_wins(self):
        for deny, expected_tools, expected_allow in (
            ('Write', 'Bash,Read', GIT_RULE + ',Read'),
            ('Bash', 'Read', 'Read'),
            ('Bash(*)', 'Read', 'Read'),
            (GIT_RULE, 'Bash,Read', 'Read'),
        ):
            with self.subTest(deny=deny):
                actual = options(normalize_claude_arguments(
                    ['--tools', 'Bash,Read,Write', '--allowedTools', 'Bash,Read,Write'],
                    ['--allowedTools', GIT_RULE + ',Read', '--disallowedTools', deny],
                    ['--tools', 'Read,Bash'],
                ))
                self.assertEqual(expected_tools, actual['--tools'])
                self.assertEqual(expected_allow, actual['--allowedTools'])
                self.assertNotIn('Bash', actual['--allowedTools'].split(','))

    def test_aliases_variadic_and_inline_arguments_preserve_patterns(self):
        actual = options(normalize_claude_arguments(
            ['--tools=Read,Bash', '--allowed-tools', 'Read', GIT_RULE,
             '--allowedTools=' + GIT_RULE + ',Read', '--disallowed-tools', 'Write', 'Edit'],
        ))
        self.assertEqual(GIT_RULE + ',Read', actual['--allowedTools'])
        self.assertEqual('Edit,Write', actual['--disallowedTools'])
        actual = options(normalize_claude_arguments(['--allowedTools', 'Bash(echo a,b) Read']))
        self.assertEqual('Bash(echo a,b),Read', actual['--allowedTools'])

    def test_empty_intersections_do_not_restore_default_tools(self):
        actual = normalize_claude_arguments(
            ['--tools', 'Read', '--allowedTools', 'Bash(git *)'],
            ['--tools', 'Bash', '--allowedTools', GIT_RULE],
        )
        self.assertEqual({'--tools': '', '--allowedTools': ''}, options(actual))
        self.assertNotIn('', actual)
        self.assertEqual(actual, normalize_claude_arguments(actual))
        self.assertEqual('Read', options(normalize_claude_arguments(
            ['--tools', 'default'], ['--tools', 'Read']))['--tools'])

    def test_path_scopes_are_not_treated_as_universal_grants(self):
        actual = options(normalize_claude_arguments(
            ['--tools', 'Read', '--allowedTools', 'Read(*)'],
            ['--allowedTools', 'Read(/src/**)'],
        ))
        self.assertEqual('', actual['--allowedTools'])
        self.assertEqual('Read', actual['--tools'])
        actual = options(normalize_claude_arguments(
            ['--tools', 'Read', '--allowedTools', 'Read', '--disallowedTools', 'Read(*)']))
        self.assertEqual('Read', actual['--tools'])
        self.assertEqual('Read(*)', actual['--disallowedTools'])

    def test_builtin_tool_ceiling_does_not_drop_mcp_permission_rules(self):
        actual = options(normalize_claude_arguments(
            ['--tools', 'Read', '--allowedTools', 'Read,mcp__example__inspect']))
        self.assertEqual('Read,mcp__example__inspect', actual['--allowedTools'])

    def test_singletons_choose_noninteractive_denial_or_reject_conflict(self):
        actual = options(normalize_claude_arguments(
            ['--permission-mode=acceptEdits', '--permission-prompts', 'host'],
            ['--permission-mode', 'dontAsk', '--permission-prompts=none'],
        ))
        self.assertEqual({'--permission-mode': 'dontAsk', '--permission-prompts': 'none'}, actual)
        with self.assertRaisesRegex(ClaudePolicyError, 'conflicting'):
            normalize_claude_arguments(['--permission-mode', 'plan', '--permission-mode', 'dontAsk'])

    def test_unknown_obsolete_and_malformed_tools_fail_before_serialization(self):
        for option in ('--tools', '--allowedTools', '--disallowedTools'):
            for name in ('MultiEdit', 'Task', 'ImaginaryTool'):
                with self.subTest(option=option, name=name), self.assertRaisesRegex(ClaudePolicyError, 'unsupported Claude tool'):
                    normalize_claude_arguments([option, name])
        for arguments in (['--tools'], ['--tools', 'Bash(git *)'],
                          ['--allowedTools', 'Bash(git *'], ['--tools', 'default,Read']):
            with self.subTest(arguments=arguments), self.assertRaises(ClaudePolicyError):
                normalize_claude_arguments(arguments)
        self.assertEqual(['--disallowedTools', 'mcp__example__*'],
                         normalize_claude_arguments(['--disallowedTools', 'mcp__example__*']))

    def test_unrelated_repeatable_options_are_preserved(self):
        arguments = ['--plugin-dir', 'first', '--plugin-dir', 'second', '--effort', 'high']
        self.assertEqual(arguments, normalize_claude_arguments(arguments))


class ClaudeRecipePolicyTest(unittest.TestCase):
    repository = fixtures.CliIntegrationTest.repository
    initialize = fixtures.CliIntegrationTest.initialize
    add_command = fixtures.CliIntegrationTest.add_command
    run_cli = fixtures.CliIntegrationTest.run_cli

    def test_invocation_session_and_profile_restrictions_join_command_policy(self):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, 'codex', 'claude')
            self.add_command(root)
            engine = root / 'engine'
            for directory in ('adapters', 'schemas'):
                shutil.copytree(fixtures.ENGINE / directory, engine / directory)
            (root / '.ai-evo').unlink()
            (root / '.ai-evo').symlink_to(engine, target_is_directory=True)
            path = engine / 'adapters/claude.yaml'
            adapter = yaml.safe_load(path.read_text())
            adapter['invocation']['command'] += [
                '--tools', 'Read,Bash,Write', '--allowedTools', 'Read,Bash,Write',
                '--permission-mode', 'acceptEdits', '--permission-prompts', 'host']
            adapter['session-translation'] = {
                reuse: ['--disallowedTools', 'Read'] for reuse in ('never', 'correction-only', 'always')}
            path.write_text(yaml.safe_dump(adapter))
            result = self.run_cli(root, 'command', 'plan', 'abc-inspect', '--adapter', 'claude')
            self.assertEqual(0, result.returncode, result.stderr)
            plan = json.loads(result.stdout)
            validate_plan(plan)
            actual = options(plan['application']['cli_arguments'])
            self.assertEqual(['claude'], plan['application']['command'])
            self.assertEqual('Bash', actual['--tools'])
            self.assertEqual(GIT_RULE, actual['--allowedTools'])
            self.assertEqual('dontAsk', actual['--permission-mode'])
            self.assertEqual('none', actual['--permission-prompts'])
            self.assertIn('Read', actual['--disallowedTools'].split(','))

            adapter['profile-translation']['delegated-cli']['resource-tools']['subagents'] = ['MultiEdit']
            path.write_text(yaml.safe_dump(adapter))
            for command in (('profile', 'resolve'), ('command', 'plan', 'abc-inspect')):
                result = self.run_cli(root, *command, '--adapter', 'claude')
                self.assertEqual(1, result.returncode)
                self.assertEqual('', result.stdout)
                self.assertIn("unsupported Claude tool 'MultiEdit'", result.stderr)

    def test_existing_resource_profiles_remain_compatible(self):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, 'claude')
            self.add_command(root)
            path = root / '.ai-evo-prj/skills/config/effort-profiles/abc-default.yaml'
            profile = yaml.safe_load(path.read_text())
            for network, subagents in itertools.product(('disabled', 'enabled', 'auto'), repeat=2):
                with self.subTest(network=network, subagents=subagents):
                    profile['resources'].update(network=network, subagents=subagents)
                    path.write_text(yaml.safe_dump(profile))
                    result = self.run_cli(root, 'command', 'plan', 'abc-inspect', '--adapter', 'claude')
                    self.assertEqual(0, result.returncode, result.stderr)
                    actual = options(json.loads(result.stdout)['application']['cli_arguments'])
                    self.assertEqual('Bash,Glob,Grep,Read', actual['--tools'])
                    self.assertEqual(GIT_RULE + ',Glob,Grep,Read', actual['--allowedTools'])
                    denied = actual['--disallowedTools'].split(',')
                    self.assertEqual(subagents == 'disabled', 'Agent' in denied)
                    self.assertIn('WebFetch', denied)
                    self.assertIn('WebSearch', denied)

    def test_review_recipe_plan_without_external_catalog(self):
        temporary, root = self.repository()
        with temporary:
            self.initialize(root, 'codex', 'claude')
            self.add_command(root)
            command = root / '.ai-evo-prj/skills/catalog/commands/abc-inspect/SKILL.md'
            body = fixtures.VALID_COMMAND.replace(
                'inputs: {}', 'inputs:\n  target: {description: Git target, default: current}\n'
                '  base: {description: Base branch, default: master}\n'
                '  focus: {description: Review focus, default: general}\n'
                '  constraints: {description: Extra constraints, default: ""}')
            command.write_text(body)
            recipe = root / '.ai-evo-prj/skills/catalog/recipes/abc-recipe-flow'
            recipe.mkdir()
            (recipe / 'SKILL.md').write_text(fixtures.VALID_FLOW_SKILL)
            (recipe / 'recipe.yaml').write_text(yaml.safe_dump({
                'version': '1.0', 'name': 'abc-recipe-flow', 'inputs': {},
                'steps': [{'id': 'review', 'uses': 'abc-inspect', 'executor': 'claude', 'with': {
                    'target': 'current', 'base': 'master', 'focus': 'general', 'constraints': ''}}],
                'outputs': {'result': {'value': '${{ steps.review.output }}'}},
            }))
            result = self.run_cli(root, 'recipe', 'plan', 'abc-recipe-flow', '--adapter', 'codex')
            self.assertEqual(0, result.returncode, result.stderr)
            step = json.loads(result.stdout)['execution']['steps'][0]
            validate_plan(step)
            actual = options(step['application']['cli_arguments'])
            self.assertEqual('Bash,Glob,Grep,Read', actual['--tools'])
            self.assertEqual(GIT_RULE + ',Glob,Grep,Read', actual['--allowedTools'])
            self.assertEqual('Agent,Edit,NotebookEdit,WebFetch,WebSearch,Write', actual['--disallowedTools'])
            self.assertEqual('dontAsk', actual['--permission-mode'])
            self.assertEqual('none', actual['--permission-prompts'])
            self.assertTrue(actual['-p'])
            self.assertTrue(actual['--strict-mcp-config'])

            # Network-only restrictions must continue to permit native edits.
            command.write_text(body.replace('workspace: read-only', 'workspace: read-write'))
            result = self.run_cli(root, 'recipe', 'plan', 'abc-recipe-flow', '--adapter', 'codex')
            self.assertEqual(0, result.returncode, result.stderr)
            step = json.loads(result.stdout)['execution']['steps'][0]
            validate_plan(step)
            actual = options(step['application']['cli_arguments'])
            for name in ('Edit', 'Write', 'NotebookEdit'):
                self.assertIn(name, actual['--tools'].split(','))
                self.assertIn(name, actual['--allowedTools'].split(','))
                self.assertNotIn(name, actual['--disallowedTools'].split(','))
