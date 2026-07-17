# Findings Rollup Tab — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Findings" tab that renders `audit_state.json` findings into one sprint-plannable, severity-sorted list.

**Architecture:** A new `tools/findings_rollup.py` renders `<date>/audit_state.json` → `<date>/findings.md`; `("findings.md", "Findings")` is added to the canonical `tools/tabs.py` manifest (2nd tab) so it flows through both `generate.sh` and `html_report`; the SKILL's Phase 2 runs it each run.

**Tech Stack:** Python 3 stdlib (+ imports `tools.tabs`), `pytest`.

## Global Constraints

- `tools/tabs.py` is the single source of truth for tabs; the new tab is added there (never hardcoded elsewhere). Manifest becomes **14** entries.
- Severity order: **Critical < High < Medium < Low < Info**; unknown severities rank after Low, before Info.
- `Info` findings are shown in a separate "Informational" section, not in "Action items".
- Domain column = the finding's `tab` mapped to its manifest title (`<tab>.md` → title), falling back to the raw `tab` string.
- Table cells escape `|` as `\|` and collapse newlines to spaces so a multi-line statement stays one row.
- Stdlib only; invoked `python3 -m tools.findings_rollup <date> [analysis_dir]`.

## File Structure

- `tools/findings_rollup.py` — `render_findings`, `main`. (Create)
- `tools/findings_rollup.sh` — wrapper. (Create)
- `tools/tabs.py` — insert `("findings.md", "Findings")` at index 1. (Modify)
- `generate-security-analysis-report/SKILL.md` — Phase-2 step. (Modify)
- `tests/test_findings_rollup.py` — new. `tests/test_tabs.py` — modify to 14.

---

### Task 1: `tools/findings_rollup.py` (render + CLI)

**Files:** Create `tools/findings_rollup.py`, `tools/findings_rollup.sh`; Test `tests/test_findings_rollup.py`.

**Interfaces:**
- Consumes: `tools.tabs.TABS`.
- Produces: `render_findings(findings: list[dict]) -> str`; `main(argv=None) -> int`;
  `SEVERITY_ORDER: dict[str, int]`.

- [ ] **Step 1: Write the failing tests** — `tests/test_findings_rollup.py`:
```python
from tools.findings_rollup import render_findings, main

F = [
    {"id": "SEC-003", "tab": "secrets_token_brokering", "statement": "key leak",
     "severity": "Critical", "evidence": "role.yaml:42", "tracking": "UNTRACKED"},
    {"id": "NET-001", "tab": "runtime_hardening_network", "statement": "open egress",
     "severity": "Medium", "evidence": "np.yaml:1", "tracking": "UNTRACKED"},
    {"id": "ARCH-001", "tab": "architectural_summary", "statement": "single-agent model",
     "severity": "Info", "evidence": "agents/", "tracking": "UNTRACKED"},
]


def test_summary_counts():
    out = render_findings(F)
    assert "**3 findings**" in out
    assert "1 Critical" in out and "1 Medium" in out and "1 Info" in out


def test_severity_sort_critical_before_medium():
    out = render_findings(F)
    assert out.index("SEC-003") < out.index("NET-001")


def test_info_is_separated():
    out = render_findings(F)
    assert "## Action items" in out and "## Informational" in out
    assert out.index("SEC-003") < out.index("## Informational")   # action items above
    assert out.index("## Informational") < out.index("ARCH-001")  # Info below the header


def test_domain_title_mapping_and_fallback():
    out = render_findings([
        {"id": "X", "tab": "secrets_token_brokering", "statement": "s",
         "severity": "High", "evidence": "e", "tracking": "t"},
        {"id": "Y", "tab": "unknown_tab", "statement": "s",
         "severity": "High", "evidence": "e", "tracking": "t"},
    ])
    assert "Secrets & Token Brokering" in out   # mapped from the manifest
    assert "unknown_tab" in out                 # fallback to raw tab


def test_cell_escapes_pipe_and_newline():
    out = render_findings([{"id": "P", "tab": "threat_model", "statement": "a|b\nc",
                            "severity": "High", "evidence": "e", "tracking": "t"}])
    row = [ln for ln in out.splitlines() if ln.startswith("| P ")][0]
    assert "a\\|b c" in row     # pipe escaped, newline collapsed -> still one row


def test_empty_findings():
    out = render_findings([])
    assert "**0 findings**" in out and "No findings recorded" in out


def test_main_writes_findings(tmp_path):
    run = tmp_path / "2026-07-16"; run.mkdir()
    (run / "audit_state.json").write_text(
        '{"generated_at":"2026-07-16","kube_agents_ref":"x",'
        '"install_namespace":"kubeagents-system","agents":["platform"],'
        '"findings":[{"id":"SEC-003","tab":"secrets_token_brokering","statement":"key leak",'
        '"severity":"Critical","evidence":"role.yaml:42","tracking":"UNTRACKED"}]}',
        encoding="utf-8")
    assert main(["2026-07-16", str(tmp_path)]) == 0
    md = (run / "findings.md").read_text(encoding="utf-8")
    assert "SEC-003" in md and "## Action items" in md


def test_main_missing_state_writes_note(tmp_path):
    run = tmp_path / "2026-07-16"; run.mkdir()
    assert main(["2026-07-16", str(tmp_path)]) == 0
    assert "No `audit_state.json`" in (run / "findings.md").read_text(encoding="utf-8")
```

- [ ] **Step 2: Run — verify fail**: `python3 -m pytest tests/test_findings_rollup.py -q` → `ModuleNotFoundError`.

- [ ] **Step 3: Implement `tools/findings_rollup.py`**:
```python
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
```

- [ ] **Step 4: Run — verify pass**: `python3 -m pytest tests/test_findings_rollup.py -q` → all pass.

- [ ] **Step 5: Wrapper + commit** — `tools/findings_rollup.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 -m tools.findings_rollup "$@"
```
```bash
chmod +x tools/findings_rollup.sh
git add tools/findings_rollup.py tools/findings_rollup.sh tests/test_findings_rollup.py
git commit -m "feat(tools): findings_rollup — audit_state.json -> sprint-plannable findings.md"
```

---

### Task 2: Add "Findings" to the manifest

**Files:** Modify `tools/tabs.py`; Modify `tests/test_tabs.py`.

**Interfaces:** Consumes/extends `tools.tabs.TABS`.

- [ ] **Step 1: Update the tabs tests** — in `tests/test_tabs.py`, replace the body of `test_manifest_has_13_tabs_in_order` with a 14-tab version and add the Findings assertion:
```python
def test_manifest_has_14_tabs_in_order():
    assert len(TABS) == 14
    assert TABS[0] == ("whats_changed.md", "What's Changed")
    assert TABS[1] == ("findings.md", "Findings")
    assert TABS[-1] == ("corrections_feedback.md", "Corrections & Feedback")
    names = [f for f, _ in TABS]
    assert len(set(names)) == 14
    assert all(f.endswith(".md") for f in names)
```
Also update `test_main_prints_tab_lines`: change `assert len(lines) == 13` to `== 14`, and after the `lines[0]` assertion add `assert lines[1] == "findings.md\tFindings"`.

- [ ] **Step 2: Run — verify fail**: `python3 -m pytest tests/test_tabs.py -q`
  Expected: FAIL (`TABS` still has 13 entries; index 1 is `architectural_summary.md`).

- [ ] **Step 3: Edit `tools/tabs.py`** — insert the Findings entry as the second item:
```python
    ("whats_changed.md", "What's Changed"),
    ("findings.md", "Findings"),
    ("architectural_summary.md", "Architectural & Security Summary"),
```
(Leave the remaining 11 entries unchanged.)

- [ ] **Step 4: Run — verify pass**:
```
python3 -m pytest tests/test_tabs.py -q         # passes
python3 -m pytest tests/test_generate_sh.py -q  # unaffected, still passes
python3 -m tools.tabs | wc -l                   # prints 14
python3 -m pytest -q                            # full suite green
```

- [ ] **Step 5: Commit**:
```bash
git add tools/tabs.py tests/test_tabs.py
git commit -m "feat(tabs): add Findings as the 2nd tab in the manifest"
```

---

### Task 3: Wire into the SKILL + roll out tonight's report

**Files:** Modify `generate-security-analysis-report/SKILL.md`.

- [ ] **Step 1: Add the Phase-2 step** — in `SKILL.md`, in the Phase 2 section alongside the corrections/What's-Changed steps, add:
```markdown
- **Findings rollup.** After `audit_state.json` is written and validated, render
  the sprint-plannable Findings tab:
  `cd "${ANALYSIS_DIR}" && python3 -m tools.findings_rollup "<date>" "${ANALYSIS_DIR}"`
```

- [ ] **Step 2: Verify the SKILL has no stray tab-count claims** — `grep -n '13 tab\|13 date' generate-security-analysis-report/SKILL.md` (fix any hit to 14; if none, nothing to do).

- [ ] **Step 3: Roll out for tonight** — generate the tab for the real run and rebuild the HTML report:
```
python3 -m tools.findings_rollup 2026-07-16 .
python3 -m tools.html_report 2026-07-16 .
```
Expected: `wrote 2026-07-16/findings.md (71 findings)` and `wrote 2026-07-16/report.html`.
Manual check: open `2026-07-16/report.html`, click the **Findings** tab (2nd) — a
summary line + a Critical-first Action-items table + an Informational section.

- [ ] **Step 4: Commit**:
```bash
git add generate-security-analysis-report/SKILL.md
git commit -m "feat(skill): render the Findings rollup in Phase 2"
```

---

## Self-Review

**Spec coverage:** findings_rollup render+CLI (spec §4,§5) → Task 1; manifest insert at index 1 & 14-tab tests (spec §4) → Task 2; SKILL Phase-2 wiring (spec §4) + tonight's rollout (spec §8) → Task 3. Edge cases (spec §6: missing/invalid state, empty findings, unknown severity via `_rank` default, unmapped tab via `_domain` fallback) → covered in Task 1 code + tests. ✓

**Placeholder scan:** every code block is complete; commands have expected output. No TBDs.

**Type consistency:** `render_findings(list[dict])->str`, `main(argv)->int`, `SEVERITY_ORDER`, `_rank`/`_domain`/`_cell`/`_summary` used consistently; `TABS` (list[tuple[str,str]]) consumed as in the manifest.
