"""Snapshot and enforce a command's structured result at the execution boundary."""
from __future__ import annotations

import json
import re
from pathlib import Path
import shutil
import sys
import tempfile

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError

from .execution import ExecutionError, ExecutionTimeout, run_delegated


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def constant(value):
        raise ValueError(f"invalid JSON constant: {value}")

    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def check_schema(schema):
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise ExecutionError(f"invalid output schema: {exc.message}") from exc
    if not isinstance(schema, dict) or schema.get("type") not in ("object", "array"):
        raise ExecutionError("output schema must describe an object or array")

    def visit(node):
        if isinstance(node, dict):
            if "$ref" in node:
                ref = node["$ref"]
                if ref != "#" and not ref.startswith("#/"):
                    raise ExecutionError("output schema supports only local JSON-pointer references")
                target = schema
                try:
                    for part in ref[2:].split("/") if ref != "#" else []:
                        target = target[part.replace("~1", "/").replace("~0", "~")]
                except (KeyError, TypeError):
                    raise ExecutionError(f"unresolved output schema reference: {ref}") from None
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)
    visit(schema)


def load_output_schema(skill_path, relative):
    if not isinstance(relative, str) or not relative.startswith("references/"):
        raise ExecutionError("output-schema must name a JSON file under references/")
    root = skill_path.parent.resolve()
    path = root / relative
    if not path.resolve().is_relative_to(root / "references") or path.is_symlink():
        raise ExecutionError("output-schema must stay inside the skill references directory")
    try:
        schema = strict_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ExecutionError(f"cannot load output-schema {relative}: {exc}") from exc
    check_schema(schema)
    return schema


def decode_result(raw, schema):
    text = raw.decode("utf-8")
    try:
        value = strict_json(text)
    except ValueError:
        # Accept one explicitly delimited JSON block, never guess boundaries
        # from the first/last brace or choose among multiple candidates.
        fences = list(re.finditer(r"(?m)^ {0,3}(`{3,}|~{3,})([^\r\n]*)\r?$", text))
        if len(fences) != 2:
            raise ValueError("expected a single JSON object/array or exactly one fenced JSON block") from None
        start, end = fences
        if (start[1] != end[1] or start[2].strip().lower() not in ("", "json")
                or end[2].strip()):
            raise ValueError("invalid JSON fence: expected matching delimiters and a json or empty language label")
        surrounding = text[:start.start()] + text[end.end():]
        # Brackets in Markdown links are prose, not JSON candidates. Use the
        # JSON parser to detect additional objects/arrays, independent of schema.
        decoder = json.JSONDecoder()
        for match in re.finditer(r"[\[{]", surrounding):
            try:
                candidate, _ = decoder.raw_decode(surrounding, match.start())
            except ValueError:
                continue
            if isinstance(candidate, (dict, list)):
                raise ValueError("ambiguous output: multiple JSON candidates")
        value = strict_json(text[start.end():end.start()])
    error = next(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value), None)
    if error:
        path = "/" + "/".join(str(part).replace("~", "~0").replace("/", "~1") for part in error.absolute_path)
        raise ValueError(f"output schema violation at {path}: {error.message}")
    return value


def execute_structured(argv, *, contract, artifacts_dir=None, **kwargs):
    # A fresh directory per attempt prevents accidental loss of previous evidence.
    if artifacts_dir:
        artifacts = Path(artifacts_dir).absolute()
        artifacts.mkdir(parents=True, exist_ok=False)
    else:
        artifacts = Path(tempfile.mkdtemp(prefix="ai-evo-execution-"))
    print(f"execution artifacts: {artifacts}", file=sys.stderr, flush=True)
    native_status = None
    status = 1
    diagnostic = {}
    payload = None
    with (artifacts / "native.stdout").open("wb") as out, (artifacts / "native.stderr").open("wb") as err:
        try:
            native_status = run_delegated(argv, stdout=out, stderr=err, **kwargs)
            status = native_status
            if native_status:
                diagnostic = {"code": "native-execution-failed", "message": f"native CLI exited with {native_status}"}
            else:
                value = decode_result((artifacts / "native.stdout").read_bytes(), contract["schema"])
                # Finish serialization before emitting any bytes or success.
                payload = (json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
        except ExecutionTimeout as exc:
            status = 124
            diagnostic = {"code": "execution-timeout", "message": str(exc)}
        except (ExecutionError, ValueError, OSError) as exc:
            status = 1
            diagnostic = {"code": "invalid-output" if native_status == 0 else "execution-failed", "message": str(exc)}
    try:
        with (artifacts / "native.stderr").open("rb") as source:
            shutil.copyfileobj(source, sys.stderr.buffer)
        sys.stderr.buffer.flush()
        if status:
            # Failed extraction must not replace the original evidence.
            with (artifacts / "native.stdout").open("rb") as source:
                shutil.copyfileobj(source, sys.stdout.buffer)
        else:
            sys.stdout.buffer.write(payload)
        sys.stdout.buffer.flush()
    except OSError as exc:
        if status == 0:
            status = 1
            diagnostic = {"code": "output-delivery-failed", "message": str(exc)}
        else:
            diagnostic["delivery_error"] = str(exc)
    # Record success only after serialization, writing and flushing succeeded.
    diagnostic.update(native_exit_code=native_status, exit_code=status)
    (artifacts / "diagnostic.json").write_text(json.dumps(diagnostic, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    if status:
        try:
            print(f"error: {diagnostic['code']}: {diagnostic['message']} (native exit {native_status})", file=sys.stderr, flush=True)
        except OSError:
            pass  # The durable diagnostic remains available if stderr is closed.
    return status
