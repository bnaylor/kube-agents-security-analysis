"""Hand-rolled validation for the Phase-1 audit_state.json ground-truth file."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REQUIRED_TOP: dict[str, type] = {
    "generated_at": str,
    "kube_agents_ref": str,
    "install_namespace": str,
    "agents": list,
    "findings": list,
}

FINDING_REQUIRED: dict[str, type] = {
    "id": str,
    "tab": str,
    "statement": str,
    "severity": str,
    "evidence": str,
}


def validate_state(data: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["top-level audit_state must be an object"]
    for key, typ in REQUIRED_TOP.items():
        if key not in data:
            errors.append(f"missing required top-level key: {key}")
        elif not isinstance(data[key], typ):
            errors.append(f"key {key} must be {typ.__name__}")
    agents = data.get("agents", [])
    if isinstance(agents, list):
        for i, agent in enumerate(agents):
            if not isinstance(agent, str):
                errors.append(f"agents[{i}] must be str")
    findings = data.get("findings", [])
    if isinstance(findings, list):
        for i, finding in enumerate(findings):
            if not isinstance(finding, dict):
                errors.append(f"findings[{i}] must be an object")
                continue
            for key, typ in FINDING_REQUIRED.items():
                if key not in finding:
                    errors.append(f"findings[{i}] missing field: {key}")
                elif not isinstance(finding[key], typ):
                    errors.append(f"findings[{i}].{key} must be {typ.__name__}")
    return errors


def load_and_validate(path: Path) -> list[str]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read/parse {path}: {exc}"]
    return validate_state(data)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        sys.stderr.write("usage: validate_state <audit_state.json>\n")
        return 2
    errors = load_and_validate(Path(argv[0]))
    for e in errors:
        sys.stderr.write(f"ERROR: {e}\n")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
