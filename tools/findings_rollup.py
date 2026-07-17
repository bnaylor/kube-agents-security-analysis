"""Render a run's audit_state.json findings into a sprint-plannable findings.md
tab: a summary line, a severity-sorted Action-items table, and a separated
Informational section. Each row's ID is the handle to grab at sprint planning."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from tools.tabs import TABS

SEVERITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3, "Info": 5}
_UNKNOWN_RANK = 4  # unknown severities sort after Low, before Info
_KNOWN = ["Critical", "High", "Medium", "Low", "Info"]
_TITLE_BY_TAB = {fname[:-3]: title for fname, title in TABS}  # "threat_model" -> "Threat Model"


def _rank(sev: str) -> int:
    return SEVERITY_ORDER.get(sev, _UNKNOWN_RANK)


def _domain(finding: dict) -> str:
    tab = finding.get("tab", "")
    return _TITLE_BY_TAB.get(tab, tab or "—")


def _cell(text) -> str:
    return str(text).replace("\r", " ").replace("\n", " ").replace("|", "\\|").strip()


def _summary(findings: list[dict]) -> str:
    counts: dict[str, int] = {}
    for f in findings:
        s = f.get("severity", "?")
        counts[s] = counts.get(s, 0) + 1
    segs = [f"{counts[s]} {s}" for s in _KNOWN if counts.get(s)]
    segs += [f"{counts[s]} {s}" for s in counts if s not in _KNOWN]
    return " · ".join(segs)


def render_findings(findings: list[dict]) -> str:
    total = len(findings)
    summary = _summary(findings)
    out = ["# Findings", ""]
    out.append(f"**{total} finding{'' if total == 1 else 's'}**"
               + (f" — {summary}" if summary else ""))
    out.append("")
    if total == 0:
        out.append("_No findings recorded for this run._")
        return "\n".join(out) + "\n"
    out += ["Grab one by **ID** at sprint planning.", "", "## Action items", ""]
    out.append("| ID | Severity | Domain | Finding | Evidence | Tracking |")
    out.append("|----|----------|--------|---------|----------|----------|")
    action = sorted((f for f in findings if f.get("severity") != "Info"),
                    key=lambda f: (_rank(f.get("severity", "")), str(f.get("id", ""))))
    for f in action:
        out.append("| {i} | {s} | {d} | {t} | {e} | {k} |".format(
            i=_cell(f.get("id", "")), s=_cell(f.get("severity", "")),
            d=_cell(_domain(f)), t=_cell(f.get("statement", "")),
            e=_cell(f.get("evidence", "")), k=_cell(f.get("tracking", ""))))
    info = [f for f in findings if f.get("severity") == "Info"]
    if info:
        out += ["", "## Informational", "", "| ID | Domain | Note |", "|----|--------|------|"]
        for f in info:
            out.append("| {i} | {d} | {t} |".format(
                i=_cell(f.get("id", "")), d=_cell(_domain(f)), t=_cell(f.get("statement", ""))))
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        sys.stderr.write("usage: findings_rollup <date> [analysis_dir]\n")
        return 2
    date = argv[0]
    analysis_dir = Path(argv[1] if len(argv) > 1 else os.environ.get("ANALYSIS_DIR", "."))
    run_dir = analysis_dir / date
    run_dir.mkdir(parents=True, exist_ok=True)
    out_path = run_dir / "findings.md"
    state = run_dir / "audit_state.json"
    findings = None
    if state.exists():
        try:
            data = json.loads(state.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("findings"), list):
                findings = data["findings"]
        except (OSError, json.JSONDecodeError):
            findings = None
    if findings is None:
        out_path.write_text("# Findings\n\n_No `audit_state.json` for this run._\n",
                            encoding="utf-8")
        sys.stdout.write(f"wrote {out_path} (no findings data)\n")
        return 0
    out_path.write_text(render_findings(findings), encoding="utf-8")
    sys.stdout.write(f"wrote {out_path} ({len(findings)} findings)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
