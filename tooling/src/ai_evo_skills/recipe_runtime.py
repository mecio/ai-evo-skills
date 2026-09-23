"""Deterministic transitions for sequential recipes; never starts an AI process."""
from __future__ import annotations

from copy import deepcopy
import hashlib
from functools import lru_cache
from importlib.resources import files
import json
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from .execution import ExecutionError, validate_plan, validate_step_consistency
from .naming import recipe_name_error


@lru_cache(maxsize=1)
def runtime_validator() -> Draft202012Validator:
    resources = files('ai_evo_skills')
    schema = json.loads(resources.joinpath('recipe-runtime.schema.json').read_text(encoding='utf-8'))
    # Derive the planned-step contract from the executable snapshot so fields
    # cannot drift. Only unresolved inputs, conditions and current mode differ.
    planned = json.loads(resources.joinpath('execution-plan.schema.json').read_text(encoding='utf-8'))
    planned['$id'] = 'urn:ai-evo-skills:schema:planned-step:1.0'
    planned['properties']['with']['additionalProperties'] = {'$ref': schema['$id'] + '#/$defs/value'}
    planned['properties']['when'] = {'$ref': schema['$id'] + '#/$defs/conditionSet'}
    planned['properties']['application']['properties']['mode'] = {'enum': ['current', 'delegated']}
    registry = Registry().with_resources((
        (schema['$id'], Resource.from_contents(schema)),
        (planned['$id'], Resource.from_contents(planned)),
    ))
    return Draft202012Validator(schema, registry=registry)


def validate_request(request: Any) -> None:
    if isinstance(request, dict) and isinstance(request.get('plan'), dict):
        name = request['plan'].get('recipe')
        if isinstance(name, str) and (diagnostic := recipe_name_error(name)):
            raise ExecutionError(diagnostic)
    errors = list(runtime_validator().iter_errors(request))
    if errors:
        details = '\n'.join(f"- {'.'.join(map(str, e.absolute_path)) or 'request'}: {e.message}" for e in errors)
        raise ExecutionError('invalid recipe runtime request:\n' + details)
    plan = request['plan']
    prior: set[str] = set()
    conditional = False
    iterative = False

    def validate_step_references(step: dict[str, Any], available: set[str], *, allow_item: bool) -> None:
        nonlocal conditional
        validate_step_consistency(step)
        references = list(step['with'].values())
        if 'when' in step:
            conditional = True
            references.extend(clause['value'] for clause in step['when']['all'])
        for value in references:
            if isinstance(value, dict) and value.get('type') == 'ai-evo-step-output' and value['step'] not in available:
                raise ExecutionError(f'{step["id"]}: output reference must name a previous step: {value["step"]}')
            if isinstance(value, dict) and value.get('type') == 'ai-evo-foreach-item' and not allow_item:
                raise ExecutionError(f'{step["id"]}: foreach item placeholder is outside a for_each template')

    for node in plan['execution']['steps']:
        sid = node['id']
        if sid in prior:
            raise ExecutionError(f'duplicate runtime step id {sid}')
        if 'for_each' not in node:
            validate_step_references(node, prior, allow_item=False)
            prior.add(sid)
            continue
        iterative = True
        items = node['for_each']['items']
        if isinstance(items, dict) and items.get('type') == 'ai-evo-foreach-item':
            raise ExecutionError(f'{sid}: foreach items cannot use the current item placeholder')
        if isinstance(items, dict) and items.get('type') == 'ai-evo-step-output' and items['step'] not in prior:
            raise ExecutionError(f'{sid}: for_each items must reference a previous step: {items["step"]}')
        template_prior = set(prior)
        template_ids: set[str] = set()
        for step in node['steps']:
            if step['id'] in template_prior or step['id'] in template_ids:
                raise ExecutionError(f'{sid}: duplicate foreach template step id {step["id"]}')
            validate_step_references(step, template_prior | template_ids, allow_item=True)
            template_ids.add(step['id'])
        if node['result']['step'] not in template_ids:
            raise ExecutionError(f'{sid}: foreach result must reference a template step')
        prior.add(sid)
    if conditional and plan['execution'].get('conditions') != 'exact-equals-v1':
        raise ExecutionError('conditional plans require the exact-equals-v1 capability')
    if iterative and plan['execution'].get('iterations') != 'json-array-sequential-v1':
        raise ExecutionError('for_each plans require the json-array-sequential-v1 capability')
    if plan['result']['step'] not in prior:
        raise ExecutionError('recipe result must reference an existing step')


def validate_recipe_snapshot(plan: Any) -> None:
    validate_request({'plan': plan, 'results': []})


def skipped_output(sid: str) -> dict[str, str]:
    return {'type': 'ai-evo-step-skipped', 'step': sid, 'reason': 'condition-false'}


def resolve_output(value: Any, outputs: dict[str, Any]) -> Any:
    if isinstance(value, str):
        return value
    sid = value['step']
    if sid not in outputs:
        raise ExecutionError(f'missing runtime output for step {sid}')
    output = outputs[sid]
    if value.get('type') == 'ai-evo-step-output-sha256':
        if not isinstance(output, str):
            raise ExecutionError(f'cannot hash non-string runtime output for step {sid}')
        return hashlib.sha256(output.encode('utf-8')).hexdigest()
    return output


def condition_matches(step: dict[str, Any], outputs: dict[str, Any]) -> bool:
    for clause in step.get('when', {}).get('all', []):
        value = resolve_output(clause['value'], outputs)
        if isinstance(value, str) and clause.get('normalize') == 'trim':
            value = value.strip()
        # A skipped output is a state, never the stringification of that state.
        # Evaluate outer guards first; a false guard suppresses inner evaluation.
        if not isinstance(value, str) or value != clause['equals']:
            return False
    return True


def iteration_input(item: Any) -> str:
    if isinstance(item, str):
        return item
    return json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def instantiate_iteration_value(value: Any, loop_id: str, index: int, item: Any) -> Any:
    if isinstance(value, str):
        return value
    if value.get('type') == 'ai-evo-foreach-item':
        return iteration_input(item)
    instantiated = deepcopy(value)
    prefix = loop_id + '.'
    if instantiated['step'].startswith(prefix):
        instantiated['step'] = f'{loop_id}.{index}.' + instantiated['step'][len(prefix):]
    return instantiated


def instantiate_iteration_step(step: dict[str, Any], loop_id: str, index: int, item: Any) -> dict[str, Any]:
    instantiated = deepcopy(step)
    prefix = loop_id + '.'
    if not instantiated['id'].startswith(prefix):
        raise ExecutionError(f'{loop_id}: foreach template step is outside its namespace')
    instantiated['id'] = f'{loop_id}.{index}.' + instantiated['id'][len(prefix):]
    instantiated['with'] = {
        name: instantiate_iteration_value(value, loop_id, index, item)
        for name, value in instantiated['with'].items()
    }
    if 'when' in instantiated:
        for clause in instantiated['when']['all']:
            clause['value'] = instantiate_iteration_value(clause['value'], loop_id, index, item)
    return instantiated


def advance_recipe(request: Any) -> dict[str, Any]:
    """Validate an ordered result journal and prepare exactly one next transition."""
    validate_request(request)
    plan, results = request['plan'], request['results']
    nodes = plan['execution']['steps']
    outputs: dict[str, Any] = {}
    transition = {'type': 'ai-evo-recipe-transition', 'version': '1.0'}
    cursor = 0

    def advance_step(step: dict[str, Any]) -> dict[str, Any] | None:
        nonlocal cursor
        sid = step['id']
        if cursor >= len(results):
            if not condition_matches(step, outputs):
                return {**transition, 'status': 'skipped', 'result': {
                    'step': sid, 'status': 'skipped', 'output': skipped_output(sid),
                }}
            prepared = deepcopy(step)
            prepared.pop('when', None)
            for name, value in step['with'].items():
                resolved = resolve_output(value, outputs)
                prepared['with'][name] = (resolved if isinstance(resolved, str) else
                                          json.dumps(resolved, ensure_ascii=False, sort_keys=True, separators=(',', ':')))
            if prepared['application']['mode'] == 'delegated':
                validate_plan(prepared)
            return {**transition, 'status': 'ready', 'step': prepared}
        result = results[cursor]
        if result['step'] != sid:
            raise ExecutionError(f'expected result for step {sid}; results must be a sequential prefix')
        applicable = condition_matches(step, outputs)
        if result['status'] == 'skipped':
            if applicable or result['output'] != skipped_output(sid):
                raise ExecutionError(f'{sid}: skipped result contradicts the planned condition')
        elif not applicable:
            raise ExecutionError(f'{sid}: condition is false; the step must be skipped')
        if result['status'] == 'failed':
            if cursor != len(results) - 1:
                raise ExecutionError('fail-fast forbids results after a failed step')
            return {**transition, 'status': 'failed', 'result': result}
        outputs[sid] = result['output']
        cursor += 1
        return None

    for node in nodes:
        if 'for_each' not in node:
            response = advance_step(node)
            if response is not None:
                return response
            continue
        raw_items = resolve_output(node['for_each']['items'], outputs)
        try:
            items = json.loads(raw_items) if isinstance(raw_items, str) else raw_items
        except json.JSONDecodeError as exc:
            raise ExecutionError(f'{node["id"]}: for_each items must be a JSON array: {exc}') from exc
        if not isinstance(items, list):
            raise ExecutionError(f'{node["id"]}: for_each items must be a JSON array')
        iteration_outputs = []
        for index, item in enumerate(items):
            for template in node['steps']:
                response = advance_step(instantiate_iteration_step(template, node['id'], index, item))
                if response is not None:
                    return response
            result_ref = instantiate_iteration_value(node['result'], node['id'], index, item)
            iteration_outputs.append(resolve_output(result_ref, outputs))
        outputs[node['id']] = json.dumps(
            iteration_outputs, ensure_ascii=False, sort_keys=True, separators=(',', ':')
        )

    if cursor != len(results):
        raise ExecutionError('more runtime results than planned steps')
    return {**transition, 'status': 'complete', 'output': resolve_output(plan['result'], outputs)}
