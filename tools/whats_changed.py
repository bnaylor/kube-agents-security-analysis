"""Assemble run-over-run COUNT summary for findings (identity-free).

Finds the previous dated run and produces a structured artifact with counts
and severity breakdown, indexed by git ref (no findings identity, no dir diff).
Enables run-over-run comparison without exposing finding details."""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def previous_run_dir(analysis_dir: Path, today: str) -> Path | None:
    """Return the latest dated run directory strictly before `today`, or None."""
    analysis_dir = Path(analysis_dir)
    dates = sorted(
        p.name for p in analysis_dir.iterdir()
        if p.is_dir() and _DATE_RE.match(p.name) and p.name < today
    )
    return analysis_dir / dates[-1] if dates else None


def _findings(run_dir: Path) -> list[dict]:
    state = Path(run_dir) / "audit_state.json"
    if not state.exists():
        return []
    try:
        data = json.loads(state.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    findings = data.get("findings", []) if isinstance(data, dict) else []
    return findings if isinstance(findings, list) else []


def _ref(run_dir: Path) -> str | None:
    state = Path(run_dir) / "audit_state.json"
    if not state.exists():
        return None
    try:
        data = json.loads(state.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    ref = data.get("kube_agents_ref") if isinstance(data, dict) else None
    return ref if isinstance(ref, str) else None


def _by_severity(findings: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for f in findings:
        s = f.get("severity", "?")
        counts[s] = counts.get(s, 0) + 1
    return counts


def assemble(prev_dir: Path, cur_dir: Path) -> dict:
    prev_dir, cur_dir = Path(prev_dir), Path(cur_dir)
    prev_f, cur_f = _findings(prev_dir), _findings(cur_dir)
    return {
        "previous": prev_dir.name,
        "current": cur_dir.name,
        "previous_ref": _ref(prev_dir),
        "current_ref": _ref(cur_dir),
        "previous_count": len(prev_f),
        "current_count": len(cur_f),
        "previous_by_severity": _by_severity(prev_f),
        "current_by_severity": _by_severity(cur_f),
    }


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        sys.stderr.write("usage: whats_changed <date> [analysis_dir]\n")
        return 2
    today = argv[0]
    analysis_dir = Path(argv[1] if len(argv) > 1 else os.environ.get("ANALYSIS_DIR", "."))
    prev = previous_run_dir(analysis_dir, today)
    if prev is None:
        sys.stdout.write(json.dumps(
            {"previous": None, "current": today,
             "note": "first run — no prior report to diff"}) + "\n")
        return 0
    sys.stdout.write(json.dumps(assemble(prev, analysis_dir / today), indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
