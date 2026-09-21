"""Recover a verified consecutive prefix without rewriting its source journal."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json

from .execution import ExecutionError
from .recipe_runtime import advance_recipe, validate_request, validate_recipe_snapshot
from .output_contract import strict_json
from jsonschema import Draft202012Validator, FormatChecker


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=True, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def evidence_template(source, target):
    validate_request(source)
    validate_recipe_snapshot(target)
    advance_recipe(source)
    checks = []
    for result in source["results"]:
        if result["status"] != "succeeded":
            break
        checks.append({"step": result["step"], "output_sha256": fingerprint(result["output"]),
                       "valid": False, "checked_at": datetime.now(timezone.utc).isoformat(),
                       "reason": "Validity not checked", "source_dependencies": {}, "current_dependencies": {}})
    return {"source_sha256": fingerprint(source), "target_sha256": fingerprint(target), "checks": checks}


def recover_prefix(source, target, evidence, *, session_parameter=None):
    """Evidence is supplied by the coordinator after checking dependencies/effects.

    No evidence means no reuse. A rejected result truncates the prefix; later
    evidence cannot authorize isolated results beyond that boundary.
    """
    validate_request(source)
    validate_recipe_snapshot(target)
    if source["plan"]["recipe"] != target["recipe"]:
        raise ExecutionError("recovery requires the same recipe")
    if not isinstance(evidence, dict) or set(evidence) != {"source_sha256", "target_sha256", "checks"}:
        raise ExecutionError("recovery evidence requires source_sha256, target_sha256 and checks")
    if evidence["source_sha256"] != fingerprint(source) or evidence["target_sha256"] != fingerprint(target):
        raise ExecutionError("recovery evidence does not match the source state and target plan")
    if not isinstance(evidence["checks"], list):
        raise ExecutionError("recovery checks must be an ordered list")
    candidate = {"plan": deepcopy(target), "results": []}
    prior = {"plan": source["plan"], "results": []}
    reused = []
    reason = "source exhausted"
    for index, result in enumerate(source["results"]):
        old = advance_recipe(prior)
        new = advance_recipe(candidate)
        if result["status"] != "succeeded":
            reason = "source step is not succeeded"
            break
        if old["status"] != "ready" or new["status"] != "ready":
            reason = "execution path changed or is not a ready step"
            break
        old_step, new_step = old["step"], new["step"]
        if result["step"] != old_step["id"] or result["step"] != new_step["id"]:
            reason = "step order changed"
            break
        comparable_old, comparable_new = deepcopy(old_step), deepcopy(new_step)
        # Only an explicitly named bookkeeping parameter may be rebound. It is
        # never a way to ignore functional inputs, policy or command changes.
        if session_parameter:
            for step in (comparable_old, comparable_new):
                if session_parameter in step["with"]:
                    step["with"][session_parameter] = "<recovery-session>"
        if comparable_old != comparable_new:
            reason = "resolved step changed (inputs, instructions, policy or executor)"
            break
        if index >= len(evidence["checks"]):
            reason = "validity evidence missing"
            break
        check = evidence["checks"][index]
        required = {"step", "output_sha256", "valid", "checked_at", "reason", "source_dependencies", "current_dependencies"}
        if not isinstance(check, dict) or set(check) != required:
            raise ExecutionError(f"invalid recovery check at index {index}")
        if check["step"] != result["step"] or check["output_sha256"] != fingerprint(result["output"]):
            raise ExecutionError(f"recovery check does not match output for {result['step']}")
        if type(check["valid"]) is not bool or not isinstance(check["reason"], str) or not check["reason"].strip():
            raise ExecutionError("recovery checks require a boolean valid and an explanatory reason")
        try:
            checked_at = datetime.fromisoformat(check["checked_at"].replace("Z", "+00:00"))
            if checked_at.tzinfo is None or checked_at > datetime.now(timezone.utc):
                raise ValueError("missing timezone or future date")
        except (ValueError, TypeError, AttributeError) as exc:
            raise ExecutionError(f"invalid recovery checked_at: {exc}") from exc
        before, after = check["source_dependencies"], check["current_dependencies"]
        if not check["valid"]:
            reason = "validity not confirmed"
            break
        if not all(isinstance(deps, dict) and deps and all(isinstance(k, str) and isinstance(v, str) and v for k, v in deps.items()) for deps in (before, after)):
            raise ExecutionError("recovery checks require nonempty dependency fingerprints")
        if not check["valid"] or before != after:
            reason = "dependencies/effects changed or validity not confirmed"
            break
        contract = new_step["application"].get("output_contract")
        if contract:
            try:
                value = strict_json(result["output"])
                Draft202012Validator(contract["schema"], format_checker=FormatChecker()).validate(value)
            except Exception as exc:
                reason = f"saved output no longer satisfies its contract: {exc}"
                break
        candidate["results"].append(deepcopy(result))
        prior["results"].append(result)
        reused.append({"step": result["step"], "output_sha256": fingerprint(result["output"]),
                       "source_step_sha256": fingerprint(old_step), "target_step_sha256": fingerprint(new_step),
                       "verification": deepcopy(check)})
    # Detect invalid source suffixes as well; they must never become authority.
    advance_recipe(source)
    transition = advance_recipe(candidate)
    return candidate, {"version": "1.0", "source_sha256": fingerprint(source),
                       "target_sha256": fingerprint(target), "reused": reused,
                       "stop_reason": reason, "next_step": transition.get("step", {}).get("id"),
                       "status": transition["status"]}
