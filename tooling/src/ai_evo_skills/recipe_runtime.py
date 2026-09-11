"""Deterministic transitions for sequential recipes; never starts an AI process."""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from importlib.resources import files
import json
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from .execution import ExecutionError, validate_plan, validate_step_consistency


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
    errors = list(runtime_validator().iter_errors(request))
    if errors:
        details = '\n'.join(f"- {'.'.join(map(str, e.absolute_path)) or 'request'}: {e.message}" for e in errors)
        raise ExecutionError('invalid recipe runtime request:\n' + details)
    plan = request['plan']
    prior: set[str] = set()
    conditional = False
    for step in plan['execution']['steps']:
        validate_step_consistency(step)
        sid = step['id']
        if sid in prior:
            raise ExecutionError(f'duplicate runtime step id {sid}')
        references = list(step['with'].values())
        if 'when' in step:
            conditional = True
            references.extend(clause['value'] for clause in step['when']['all'])
        for value in references:
            if isinstance(value, dict) and value['step'] not in prior:
                raise ExecutionError(f'{sid}: output reference must name a previous step: {value["step"]}')
        prior.add(sid)
    if conditional and plan['execution'].get('conditions') != 'exact-equals-v1':
        raise ExecutionError('conditional plans require the exact-equals-v1 capability')
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
    return outputs[sid]


def condition_matches(step: dict[str, Any], outputs: dict[str, Any]) -> bool:
    for clause in step.get('when', {}).get('all', []):
        value = resolve_output(clause['value'], outputs)
        # A skipped output is a state, never the stringification of that state.
        # Evaluate outer guards first; a false guard suppresses inner evaluation.
        if not isinstance(value, str) or value != clause['equals']:
            return False
    return True


def advance_recipe(request: Any) -> dict[str, Any]:
    """Validate an ordered result journal and prepare exactly one next transition."""
    validate_request(request)
    plan, results = request['plan'], request['results']
    steps = plan['execution']['steps']
    if len(results) > len(steps):
        raise ExecutionError('more runtime results than planned steps')
    outputs: dict[str, Any] = {}
    transition = {'type': 'ai-evo-recipe-transition', 'version': '1.0'}
    for step, result in zip(steps, results):
        sid = step['id']
        if result['step'] != sid:
            raise ExecutionError(f'expected result for step {sid}; results must be a sequential prefix')
        applicable = condition_matches(step, outputs)
        if result['status'] == 'skipped':
            if applicable or result['output'] != skipped_output(sid):
                raise ExecutionError(f'{sid}: skipped result contradicts the planned condition')
        elif not applicable:
            raise ExecutionError(f'{sid}: condition is false; the step must be skipped')
        if result['status'] == 'failed':
            if len(results) != len(outputs) + 1:
                raise ExecutionError('fail-fast forbids results after a failed step')
            return {**transition, 'status': 'failed', 'result': result}
        outputs[sid] = result['output']

    if len(results) == len(steps):
        return {**transition, 'status': 'complete', 'output': resolve_output(plan['result'], outputs)}
    step = steps[len(results)]
    if not condition_matches(step, outputs):
        return {**transition, 'status': 'skipped', 'result': {
            'step': step['id'], 'status': 'skipped', 'output': skipped_output(step['id']),
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
