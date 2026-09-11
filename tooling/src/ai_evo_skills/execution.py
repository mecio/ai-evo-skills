"""Validation of resolved execution snapshots, independent of the project catalog."""
from __future__ import annotations

from importlib.resources import files
import json
from typing import Any

from jsonschema import Draft202012Validator


class ExecutionError(ValueError):
    pass


def validate_plan(step: Any) -> None:
    schema = json.loads(files('ai_evo_skills').joinpath('execution-plan.schema.json').read_text(encoding='utf-8'))
    errors = list(Draft202012Validator(schema).iter_errors(step))
    if errors:
        details = '\n'.join(f"- {'.'.join(map(str, error.absolute_path)) or 'plan'}: {error.message}" for error in errors)
        raise ExecutionError('invalid execution plan; resolve all step output references before execution:\n' + details)
    app, session = step['application'], step['application']['session']
    permitted = session['reuse'] != 'never'
    supported = bool(session['resume_arguments'])
    if (session['resume_permitted'] != permitted or session['resume_supported'] != supported
            or session['resume_allowed'] != (permitted and supported)
            or session['corrections_only'] != (session['reuse'] == 'correction-only')):
        raise ExecutionError('inconsistent session capability or reuse policy')
    if app['profile']['adapter'] != app['executor']:
        raise ExecutionError('profile adapter must match the execution adapter')
    recipe = 'resolved' if 'uses' in step else 'not-applicable'
    if step['handoff']['planning']['recipe'] != recipe:
        raise ExecutionError('handoff planning status does not match the plan kind')
