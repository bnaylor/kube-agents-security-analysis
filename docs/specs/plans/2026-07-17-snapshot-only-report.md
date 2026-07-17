# Snapshot-only report — drop cross-run tracking — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the standalone security report a pure snapshot — remove the non-functional cross-run `tracking` field/column and the ID-keyed What's-Changed diff, replacing the latter with an identity-free count summary.

**Architecture:** All subtraction. Drop `tracking` from the schema, validator, and Findings table. Rewrite `whats_changed.assemble` to emit run-over-run *counts* (which need no stable identity) and retire `diff_reports.py` (its only consumer). Update the SKILL/templates/README prose so nobody re-adds tracking.

**Tech Stack:** Python 3 stdlib only, pytest (dev-only). No new dependencies. Everything stays offline.

## Global Constraints

- **Offline / stdlib-only** for the `tools/` package — no network, no new third-party deps (verbatim from the design's rationale).
- **Commits:** author `Brian Naylor <anthropic@scromp.net>`; trailer `Assisted-by: Claude Code`. **Never** add `Co-Authored-By: Claude` (CLA blocker). Use: `git -c user.name='Brian Naylor' -c user.email='anthropic@scromp.net' commit -m "<msg>

Assisted-by: Claude Code"`.
- **Do not modify** the committed `2026-07-16/` run data — it is a frozen historical artifact and keeps its `tracking: UNTRACKED` values.
- Run the suite with `python3 -m pytest` from the repo root (`/Users/bnaylor/src/work/kube-agents-security-analysis`).
- Finding IDs remain `<TAB>-NNN` but are **per-run ephemeral** (documented, not enforced).

---

### Task 1: Drop `tracking` from schema + validator

**Files:**
- Modify: `schemas/audit_state.schema.json:14` and `:21`
- Modify: `tools/validate_state.py:16-23`
- Test: `tests/test_validate_state.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `validate_state(data: object) -> list[str]` — a finding with keys `id, tab, statement, severity, evidence` (NO `tracking`) validates clean. Extra keys (e.g. a lingering `tracking`) are ignored, not errors.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_validate_state.py`:

```python
def test_finding_without_tracking_is_valid():
    data = _valid(); del data["findings"][0]["tracking"]
    assert validate_state(data) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_validate_state.py::test_finding_without_tracking_is_valid -v`
Expected: FAIL — `["findings[0] missing field: tracking"]` is non-empty, assertion fails.

- [ ] **Step 3: Remove `tracking` from the validator**

In `tools/validate_state.py`, delete the `tracking` line from `FINDING_REQUIRED` so it reads:

```python
FINDING_REQUIRED: dict[str, type] = {
    "id": str,
    "tab": str,
    "statement": str,
    "severity": str,
    "evidence": str,
}
```

- [ ] **Step 4: Remove `tracking` from the JSON schema**

In `schemas/audit_state.schema.json`, change the finding `required` array (line 14) to drop `"tracking"`:

```json
        "required": ["id", "tab", "statement", "severity", "evidence"],
```

and delete the `tracking` property line (line 21) so `properties` ends at `evidence`:

```json
          "evidence": {"type": "string", "description": "file:line"}
```

(ensure the preceding line no longer has a trailing comma issue — `evidence` is now the last property).

- [ ] **Step 5: Run the full validate_state suite**

Run: `python3 -m pytest tests/test_validate_state.py -v`
Expected: PASS (all, including the new test and the existing `_valid()` fixture which still carries a harmless `tracking` key).

- [ ] **Step 6: Commit**

```bash
git add schemas/audit_state.schema.json tools/validate_state.py tests/test_validate_state.py
git -c user.name='Brian Naylor' -c user.email='anthropic@scromp.net' commit -m "refactor(schema): drop tracking from audit_state finding contract

Assisted-by: Claude Code"
```

---

### Task 2: Remove the Tracking column from the Findings tab

**Files:**
- Modify: `tools/findings_rollup.py:52-61` (Action-items table header, separator, rows)
- Test: `tests/test_findings_rollup.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `render_findings(findings: list[dict]) -> str` — the Action-items table has exactly 5 columns `| ID | Severity | Domain | Finding | Evidence |` (no Tracking). Informational table is unchanged (already tracking-free).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_findings_rollup.py`:

```python
def test_no_tracking_column():
    out = render_findings(F)
    header = [ln for ln in out.splitlines() if ln.startswith("| ID ")][0]
    assert "Tracking" not in header
    assert header.count("|") == 6  # 5 columns -> 6 pipes
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_findings_rollup.py::test_no_tracking_column -v`
Expected: FAIL — current header has a `Tracking` column (7 pipes) and the substring "Tracking".

- [ ] **Step 3: Drop the column from the table**

In `tools/findings_rollup.py`, replace the header/separator lines and the row `.format` (currently `findings_rollup.py:53-54` and `:58-61`):

```python
    out.append("| ID | Severity | Domain | Finding | Evidence |")
    out.append("|----|----------|--------|---------|----------|")
    action = sorted((f for f in findings if f.get("severity") != "Info"),
                    key=lambda f: (_rank(f.get("severity", "")), str(f.get("id", ""))))
    for f in action:
        out.append("| {i} | {s} | {d} | {t} | {e} |".format(
            i=_cell(f.get("id", "")), s=_cell(f.get("severity", "")),
            d=_cell(_domain(f)), t=_cell(f.get("statement", "")),
            e=_cell(f.get("evidence", ""))))
```

(Remove the `| {k} |` field and the `k=_cell(f.get("tracking", ""))` argument.)

- [ ] **Step 4: Run the full findings_rollup suite**

Run: `python3 -m pytest tests/test_findings_rollup.py -v`
Expected: PASS (new test plus existing ones — fixtures still carry a `tracking` key which is now simply ignored).

- [ ] **Step 5: Commit**

```bash
git add tools/findings_rollup.py tests/test_findings_rollup.py
git -c user.name='Brian Naylor' -c user.email='anthropic@scromp.net' commit -m "refactor(findings): drop non-functional Tracking column

Assisted-by: Claude Code"
```

---

### Task 3: Count-based What's-Changed; retire diff_reports

**Files:**
- Modify: `tools/whats_changed.py` (drop `diff_reports` import; rewrite `assemble`; add `_count_by_severity`, `_ref`)
- Delete: `tools/diff_reports.py`, `tools/diff_reports.sh`, `tests/test_diff_reports.py`
- Test: `tests/test_whats_changed.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `assemble(prev_dir: Path, cur_dir: Path) -> dict` returning keys `previous, current, previous_ref, current_ref, previous_count, current_count, previous_by_severity, current_by_severity` — and **no** `dir_diff` or `findings` keys. `previous_run_dir(analysis_dir, today)` is unchanged. `main` still prints the first-run note when there is no prior run.

- [ ] **Step 1: Rewrite the assemble tests**

In `tests/test_whats_changed.py`, **replace** `test_assemble_reports_dir_and_findings_delta` and `test_assemble_tolerates_missing_audit_state` with:

```python
def test_assemble_reports_counts_and_refs(tmp_path):
    prev = tmp_path / "2026-07-15"
    cur = tmp_path / "2026-07-16"
    _mk(prev, {"audit_state.json": json.dumps({"kube_agents_ref": "old111",
        "findings": [{"id": "F-1", "severity": "High"},
                     {"id": "F-2", "severity": "Low"}]})})
    _mk(cur, {"audit_state.json": json.dumps({"kube_agents_ref": "new222",
        "findings": [{"id": "F-3", "severity": "High"}]})})
    r = assemble(prev, cur)
    assert r["previous"] == "2026-07-15" and r["current"] == "2026-07-16"
    assert r["previous_ref"] == "old111" and r["current_ref"] == "new222"
    assert r["previous_count"] == 2 and r["current_count"] == 1
    assert r["previous_by_severity"] == {"High": 1, "Low": 1}
    assert r["current_by_severity"] == {"High": 1}
    assert "dir_diff" not in r and "findings" not in r


def test_assemble_tolerates_missing_audit_state(tmp_path):
    prev = tmp_path / "2026-07-15"
    cur = tmp_path / "2026-07-16"
    _mk(prev, {"report.md": "old\n"})
    _mk(cur, {"report.md": "new\n"})
    r = assemble(prev, cur)
    assert r["previous_count"] == 0 and r["current_count"] == 0
    assert r["previous_ref"] is None and r["current_ref"] is None
    assert r["previous_by_severity"] == {} and r["current_by_severity"] == {}
```

(Leave the three `previous_run_dir` tests untouched.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_whats_changed.py -v`
Expected: the two rewritten tests FAIL (current `assemble` returns `dir_diff`/`findings`, has no `*_count`/`*_ref` keys).

- [ ] **Step 3: Rewrite `assemble` in `tools/whats_changed.py`**

Change the import line (`from tools.diff_reports import diff_dirs, diff_findings`) — **delete it**. Keep `_findings`. Add helpers and rewrite `assemble`:

```python
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
```

Update the module docstring (lines 1-6) to describe a count summary rather than a "directory diff + findings added/removed/changed."

- [ ] **Step 4: Delete the retired module, wrapper, and its test**

```bash
git rm tools/diff_reports.py tools/diff_reports.sh tests/test_diff_reports.py
```

- [ ] **Step 5: Run the whats_changed suite + confirm no dangling imports**

Run: `python3 -m pytest tests/test_whats_changed.py -v`
Expected: PASS.
Run: `grep -rn "diff_reports\|diff_findings\|diff_dirs" tools/ tests/ generate.sh generate-security-analysis-report/`
Expected: no matches (empty output).

- [ ] **Step 6: Commit**

```bash
git add tools/whats_changed.py tests/test_whats_changed.py
git -c user.name='Brian Naylor' -c user.email='anthropic@scromp.net' commit -m "refactor(whats-changed): count summary; retire ID-keyed diff_reports

Assisted-by: Claude Code"
```

---

### Task 4: Update SKILL, templates, and README prose

**Files:**
- Modify: `generate-security-analysis-report/SKILL.md` (Phase 1 field list ~line 48-51; Step 2b ~line 112-120)
- Modify: `templates/agentic_tools_mcp_trust.md:13`, `templates/threat_model.md:20`
- Modify: `README.md` (any tracking-column / What's-Changed-diff description)

**Interfaces:**
- Consumes: the final tool behavior from Tasks 1-3.
- Produces: documentation only — no code, no tests. Verified by grep + the existing smoke test.

- [ ] **Step 1: Update the SKILL Phase-1 schema description**

In `generate-security-analysis-report/SKILL.md`, in the Phase 1 paragraph that lists finding fields (currently `id, tab, statement, severity, evidence` (`file:line`), `tracking` (...)), remove the `tracking` clause and append a sentence:

> Finding IDs (`<TAB>-NNN`) are **per-run ephemeral** — a handle to point at a row in this report only, not a stable cross-run identifier.

- [ ] **Step 2: Update the SKILL Step 2b (What's Changed)**

Replace the Step 2b description so it reflects the count summary. The tool now emits `previous/current` counts, per-severity breakdowns, and refs; the agent curates a short prose note. Example wording to include:

> Curate the count summary it emits (previous/current finding counts, per-severity breakdown, and the two `kube_agents_ref` shas) into a short prose `whats_changed.md`, e.g. *"Re-audited at `abc123` (was `def456`); 61 findings, down from 82 — Critical 8→6, High 19→15."* First run (no prior report): a short "baseline — no prior run" note. Note there is **no** per-finding diff — IDs are per-run ephemeral, so run-over-run comparison is by count, not by finding identity.

- [ ] **Step 3: Reword the two template comments**

In `templates/agentic_tools_mcp_trust.md:13`, change `carry an owner/tracking link.` to `name the responsible owner.`
In `templates/threat_model.md:20`, change `Each material finding carries an owner/tracking link` to `Each material finding names a responsible owner`.
(Match surrounding sentence flow; these are HTML comments / guidance prose.)

- [ ] **Step 4: Update the README**

Run: `grep -n -i "tracking\|what's changed\|whats_changed\|diff" README.md`
For any hit that describes a Tracking column or a mechanical per-finding What's-Changed diff, update it to: the report is a **snapshot** (tracking lives in external bug tools; What's-Changed is a count-based prose summary). If there are no such hits, no change is needed.

- [ ] **Step 5: Verify no stale tracking references remain in the toolchain**

Run: `grep -rn -i "tracking" tools/ schemas/ templates/ generate-security-analysis-report/ README.md`
Expected: no references that imply a functional tracking column remain (matches, if any, should only be incidental prose you've already reconciled).

- [ ] **Step 6: Run the full suite (smoke test included)**

Run: `python3 -m pytest`
Expected: PASS (green). Note the new total = previous total − (deleted `test_diff_reports.py` cases) + (2 new assertions in Tasks 1-2).

- [ ] **Step 7: Commit**

```bash
git add generate-security-analysis-report/SKILL.md templates/agentic_tools_mcp_trust.md templates/threat_model.md README.md
git -c user.name='Brian Naylor' -c user.email='anthropic@scromp.net' commit -m "docs: reflect snapshot-only report (no tracking, count-based What's Changed)

Assisted-by: Claude Code"
```

---

## Self-Review

**Spec coverage** (each design change → task):
1. Schema drop `tracking` → Task 1 ✅
2. `validate_state` drop `tracking` → Task 1 ✅
3. `findings_rollup` drop Tracking column → Task 2 ✅
4. `whats_changed` count summary → Task 3 ✅
5. Retire `diff_reports.py` (+ `.sh`, test) → Task 3 ✅
6. SKILL Phase 1 (ephemeral IDs) + Step 2b (prose) → Task 4 ✅
7. Reword two template comments → Task 4 ✅
8. README snapshot note → Task 4 ✅
9. Rationale doc → already committed (`28df066`) ✅
- Frozen `2026-07-16/` data → Global Constraints ("do not modify") ✅

**Placeholder scan:** none — every code step shows the exact code; README step is a bounded grep-and-reconcile with an explicit fallback ("no change needed").

**Type consistency:** `assemble` return keys defined in Task 3's Interfaces match the Task 3 test and implementation (`previous_ref/current_ref/previous_count/current_count/previous_by_severity/current_by_severity`). `render_findings` 5-column contract matches Task 2's test (6 pipes). `validate_state(data: object) -> list[str]` unchanged signature.
