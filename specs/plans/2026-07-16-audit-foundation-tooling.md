# Audit Foundation Tooling — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the stdlib-only Python tools the reworked security-audit SKILL orchestrates — drift pre-flight, `audit_state.json` validation, run-over-run diffing, and the corrections ledger (with the anti-gaslighting guardrail).

**Architecture:** Each tool is an importable module under `tools/` with a thin `.sh` wrapper (`python3 -m tools.<name>`). Logic is pure-Python and pytest-tested; the SKILL and `generate.sh` (Plan 2) call the wrappers. This is Plan 1 of 2; Plan 2 (SKILL rework + 13 tab templates) consumes these signatures.

**Tech Stack:** Python 3 (standard library only at runtime), `git` (for `diff --no-index`), `pytest` (dev-only), bash wrappers.

## Global Constraints

- **Runtime deps: Python 3 standard library only.** No third-party runtime packages. `pytest` is the only dev dependency.
- **Tools are a package.** Modules live in `tools/` (a package with `__init__.py`); invoke via `python3 -m tools.<name>` from repo root. Thin `.sh` wrappers `exec` that.
- **Ledger storage (refines spec §5.1):** canonical store is `corrections/ledger.jsonl` — one JSON `Correction` object per line. `corrections/ledger.md` and the per-run `corrections_feedback.md` (Tab 12) are *rendered views* of it.
- **Anti-gaslighting guardrail (spec §5.4):** a transition to `denied` MUST carry a non-empty `proof` string, else it is rejected with `GuardrailError`.
- **Lifecycle states:** `open → confirmed | denied`; `confirmed → absorbed`; `absorbed → retired`; `denied` is terminal.
- **Fixed facts:** install namespace is `kubeagents-system`; single `platform` agent (operator/devteam removed, #256); dates are `YYYY-MM-DD` (UTC).

## File Structure

- `tools/__init__.py` — package marker (empty).
- `tools/preflight.py` — Step-0 drift checks; `run_preflight`, `DEFAULT_CHECKS`, CLI.
- `tools/preflight.sh` — wrapper.
- `tools/validate_state.py` — `audit_state.json` schema validation; `validate_state`, CLI.
- `tools/diff_reports.py` — `diff_dirs`, `diff_findings`; CLI.
- `tools/diff_reports.sh` — wrapper.
- `tools/ledger.py` — `Correction`, `transition`, load/save, `parse_inbox`, `ingest_inbox`, `render_markdown`; CLI.
- `schemas/audit_state.schema.json` — human-readable schema doc (validation is hand-rolled in `validate_state.py`).
- `tests/__init__.py`, `tests/test_*.py` — pytest suites.
- `pytest.ini`, `requirements-dev.txt`, `.gitignore` (append pycache).

---

### Task 1: Test scaffolding

**Files:**
- Create: `tools/__init__.py`, `tests/__init__.py`, `pytest.ini`, `requirements-dev.txt`
- Modify: `.gitignore`
- Test: `tests/test_smoke.py`

**Interfaces:**
- Produces: a working `pytest` harness that discovers `tests/` and imports `tools.*`.

- [ ] **Step 1: Create package/config files**

`tools/__init__.py` and `tests/__init__.py` are empty files.

`pytest.ini`:
```ini
[pytest]
testpaths = tests
```

`requirements-dev.txt`:
```
pytest>=8
```

Append to `.gitignore`:
```
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 2: Write the smoke test**

`tests/test_smoke.py`:
```python
def test_harness_runs():
    assert True
```

- [ ] **Step 3: Run it — verify pass**

Run: `python3 -m pytest -q`
Expected: `1 passed`.

- [ ] **Step 4: Commit**

```bash
git add tools/__init__.py tests/__init__.py tests/test_smoke.py pytest.ini requirements-dev.txt .gitignore
git commit -m "chore: pytest scaffolding for audit tools"
```

---

### Task 2: Pre-flight drift checker

**Files:**
- Create: `tools/preflight.py`, `tools/preflight.sh`
- Test: `tests/test_preflight.py`

**Interfaces:**
- Produces:
  - `Check(kind: str, target: str, reason: str, optional: bool = False)` — `kind` ∈ `{"file","dir","absent","command"}`; `target` is a path relative to the kube-agents repo (or a shell command for `"command"`).
  - `CheckResult(check: Check, passed: bool, skipped: bool, detail: str)`
  - `PreflightResult(results: list[CheckResult])` with `.ok: bool` and `.report_md() -> str`.
  - `evaluate_check(check: Check, base: Path) -> CheckResult`
  - `run_preflight(base: Path, checks: list[Check]) -> PreflightResult`
  - `DEFAULT_CHECKS: list[Check]`

- [ ] **Step 1: Write failing tests**

`tests/test_preflight.py`:
```python
from pathlib import Path
from tools.preflight import Check, evaluate_check, run_preflight


def test_file_check_passes_when_present(tmp_path):
    (tmp_path / "config.yaml").write_text("x")
    r = evaluate_check(Check("file", "config.yaml", "cfg"), tmp_path)
    assert r.passed and not r.skipped


def test_file_check_fails_when_missing(tmp_path):
    r = evaluate_check(Check("file", "config.yaml", "cfg"), tmp_path)
    assert not r.passed


def test_absent_check_passes_when_missing(tmp_path):
    r = evaluate_check(Check("absent", "agents/operator", "removed"), tmp_path)
    assert r.passed


def test_absent_check_fails_when_present(tmp_path):
    (tmp_path / "agents" / "operator").mkdir(parents=True)
    r = evaluate_check(Check("absent", "agents/operator", "removed"), tmp_path)
    assert not r.passed


def test_optional_command_missing_is_not_fatal(tmp_path):
    chk = Check("command", "definitely-not-a-real-binary-xyz", "opt", optional=True)
    result = run_preflight(tmp_path, [chk])
    assert result.ok is True


def test_report_md_lists_failures(tmp_path):
    result = run_preflight(tmp_path, [Check("file", "missing.yaml", "needed")])
    assert result.ok is False
    md = result.report_md()
    assert "missing.yaml" in md and "needed" in md
```

- [ ] **Step 2: Run — verify fail**

Run: `python3 -m pytest tests/test_preflight.py -q`
Expected: FAIL (`ModuleNotFoundError: tools.preflight`).

- [ ] **Step 3: Implement `tools/preflight.py`**

```python
"""Step-0 pre-flight: assert dated path-hints still resolve before analysis."""
from __future__ import annotations

import os
import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Check:
    kind: str            # "file" | "dir" | "absent" | "command"
    target: str          # path relative to base, or a shell command
    reason: str
    optional: bool = False


@dataclass
class CheckResult:
    check: Check
    passed: bool
    skipped: bool
    detail: str


@dataclass
class PreflightResult:
    results: list[CheckResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(r.passed or r.skipped or r.check.optional for r in self.results)

    def report_md(self) -> str:
        lines = ["# Pre-flight drift report", ""]
        for r in self.results:
            mark = "PASS" if r.passed else ("SKIP" if r.skipped else "FAIL")
            lines.append(f"- **{mark}** `{r.check.target}` — {r.check.reason} ({r.detail})")
        return "\n".join(lines) + "\n"


def evaluate_check(check: Check, base: Path) -> CheckResult:
    if check.kind == "command":
        exe = shlex.split(check.target)[0]
        if _which(exe) is None:
            return CheckResult(check, passed=False, skipped=True, detail="tool not present")
        proc = subprocess.run(shlex.split(check.target), capture_output=True, text=True)
        return CheckResult(check, passed=proc.returncode == 0, skipped=False,
                           detail=f"exit {proc.returncode}")
    path = base / check.target
    if check.kind == "file":
        return CheckResult(check, path.is_file(), False, "is_file")
    if check.kind == "dir":
        return CheckResult(check, path.is_dir(), False, "is_dir")
    if check.kind == "absent":
        return CheckResult(check, not path.exists(), False, "absent")
    raise ValueError(f"unknown check kind: {check.kind}")


def _which(exe: str):
    from shutil import which
    return which(exe)


def run_preflight(base: Path, checks: list[Check]) -> PreflightResult:
    return PreflightResult([evaluate_check(c, base) for c in checks])


# as of 2026-07-16 — verify each run
DEFAULT_CHECKS: list[Check] = [
    Check("file", "agents/platform/config.yaml", "single-agent model intact"),
    Check("dir", "agents/platform", "platform agent present"),
    Check("absent", "agents/operator", "operator agent removed (#256)"),
    Check("absent", "agents/devteam", "devteam agent removed (#256)"),
    Check("file", "agents/platform/scripts/platform_mcp_server.py", "MCP server path alive"),
    Check("command", "kubectl get ns kubeagents-system", "install namespace", optional=True),
]


def main(argv: list[str] | None = None) -> int:
    base = Path(os.environ.get("KUBE_AGENTS_DIR", ".")).resolve()
    result = run_preflight(base, DEFAULT_CHECKS)
    sys.stdout.write(result.report_md())
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run — verify pass**

Run: `python3 -m pytest tests/test_preflight.py -q`
Expected: all pass.

- [ ] **Step 5: Add the shell wrapper**

`tools/preflight.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 -m tools.preflight "$@"
```
Then: `chmod +x tools/preflight.sh`

- [ ] **Step 6: Commit**

```bash
git add tools/preflight.py tools/preflight.sh tests/test_preflight.py
git commit -m "feat(tools): pre-flight drift checker with hard-fail exit"
```

---

### Task 3: `audit_state.json` validator

**Files:**
- Create: `tools/validate_state.py`, `schemas/audit_state.schema.json`
- Test: `tests/test_validate_state.py`

**Interfaces:**
- Produces:
  - `validate_state(data: dict) -> list[str]` — returns error messages; empty list = valid.
  - `REQUIRED_TOP: dict[str, type]`, `FINDING_REQUIRED: dict[str, type]`
  - `load_and_validate(path: Path) -> list[str]`

- [ ] **Step 1: Write failing tests**

`tests/test_validate_state.py`:
```python
from tools.validate_state import validate_state


def _valid():
    return {
        "generated_at": "2026-07-16",
        "kube_agents_ref": "abc1234",
        "install_namespace": "kubeagents-system",
        "agents": ["platform"],
        "findings": [
            {"id": "F-001", "tab": "Tools, MCP & Inter-Agent Trust",
             "statement": "API_SERVER_KEY defaults to 'none'",
             "severity": "high", "evidence": "agent_common_server.py:29",
             "tracking": "UNTRACKED"},
        ],
    }


def test_valid_state_has_no_errors():
    assert validate_state(_valid()) == []


def test_missing_top_key_is_error():
    data = _valid(); del data["findings"]
    errs = validate_state(data)
    assert any("findings" in e for e in errs)


def test_wrong_top_type_is_error():
    data = _valid(); data["agents"] = "platform"
    errs = validate_state(data)
    assert any("agents" in e for e in errs)


def test_finding_missing_field_is_error():
    data = _valid(); del data["findings"][0]["evidence"]
    errs = validate_state(data)
    assert any("evidence" in e for e in errs)
```

- [ ] **Step 2: Run — verify fail**

Run: `python3 -m pytest tests/test_validate_state.py -q`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement `tools/validate_state.py`**

```python
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
    "tracking": str,
}


def validate_state(data: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["top-level audit_state must be an object"]
    for key, typ in REQUIRED_TOP.items():
        if key not in data:
            errors.append(f"missing required top-level key: {key}")
        elif not isinstance(data[key], typ):
            errors.append(f"key {key} must be {typ.__name__}")
    for i, finding in enumerate(data.get("findings", []) or []):
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
```

`schemas/audit_state.schema.json` (documentation of the same shape):
```json
{
  "title": "audit_state",
  "type": "object",
  "required": ["generated_at", "kube_agents_ref", "install_namespace", "agents", "findings"],
  "properties": {
    "generated_at": {"type": "string", "description": "YYYY-MM-DD UTC"},
    "kube_agents_ref": {"type": "string", "description": "git sha of the audited repo"},
    "install_namespace": {"type": "string"},
    "agents": {"type": "array", "items": {"type": "string"}},
    "findings": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "tab", "statement", "severity", "evidence", "tracking"],
        "properties": {
          "id": {"type": "string"},
          "tab": {"type": "string"},
          "statement": {"type": "string"},
          "severity": {"type": "string"},
          "evidence": {"type": "string", "description": "file:line"},
          "tracking": {"type": "string", "description": "kube-agents issue/PR link or UNTRACKED"}
        }
      }
    }
  }
}
```

- [ ] **Step 4: Run — verify pass**

Run: `python3 -m pytest tests/test_validate_state.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add tools/validate_state.py schemas/audit_state.schema.json tests/test_validate_state.py
git commit -m "feat(tools): audit_state.json validator + schema doc"
```

---

### Task 4: Run-over-run diff helpers

**Files:**
- Create: `tools/diff_reports.py`, `tools/diff_reports.sh`
- Test: `tests/test_diff_reports.py`

**Interfaces:**
- Produces:
  - `diff_dirs(old: Path, new: Path) -> str` — unified `git diff --no-index` text (empty string if identical).
  - `diff_findings(old: list[dict], new: list[dict]) -> dict` — `{"added": [...], "removed": [...], "changed": [...]}` keyed by finding `id`.

- [ ] **Step 1: Write failing tests**

`tests/test_diff_reports.py`:
```python
from tools.diff_reports import diff_dirs, diff_findings


def test_diff_dirs_reports_changed_file(tmp_path):
    old = tmp_path / "old"; new = tmp_path / "new"
    old.mkdir(); new.mkdir()
    (old / "a.md").write_text("one\n")
    (new / "a.md").write_text("two\n")
    out = diff_dirs(old, new)
    assert "a.md" in out and "two" in out


def test_diff_dirs_empty_when_identical(tmp_path):
    old = tmp_path / "old"; new = tmp_path / "new"
    old.mkdir(); new.mkdir()
    (old / "a.md").write_text("same\n")
    (new / "a.md").write_text("same\n")
    assert diff_dirs(old, new) == ""


def test_diff_findings_classifies():
    old = [{"id": "F-1", "statement": "x"}, {"id": "F-2", "statement": "y"}]
    new = [{"id": "F-2", "statement": "y2"}, {"id": "F-3", "statement": "z"}]
    d = diff_findings(old, new)
    assert [f["id"] for f in d["added"]] == ["F-3"]
    assert [f["id"] for f in d["removed"]] == ["F-1"]
    assert [f["id"] for f in d["changed"]] == ["F-2"]
```

- [ ] **Step 2: Run — verify fail**

Run: `python3 -m pytest tests/test_diff_reports.py -q`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement `tools/diff_reports.py`**

```python
"""Deterministic diff inputs for the 'What's Changed' tab."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def diff_dirs(old: Path, new: Path) -> str:
    proc = subprocess.run(
        ["git", "diff", "--no-index", "--", str(old), str(new)],
        capture_output=True, text=True,
    )
    # git diff --no-index: 0 = identical, 1 = differences, >1 = error
    if proc.returncode > 1:
        raise RuntimeError(proc.stderr.strip() or "git diff failed")
    return proc.stdout


def diff_findings(old: list[dict], new: list[dict]) -> dict:
    old_by = {f["id"]: f for f in old}
    new_by = {f["id"]: f for f in new}
    added = [new_by[i] for i in new_by if i not in old_by]
    removed = [old_by[i] for i in old_by if i not in new_by]
    changed = [new_by[i] for i in new_by if i in old_by and new_by[i] != old_by[i]]
    return {"added": added, "removed": removed, "changed": changed}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        sys.stderr.write("usage: diff_reports <old_dir> <new_dir>\n")
        return 2
    sys.stdout.write(diff_dirs(Path(argv[0]), Path(argv[1])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run — verify pass**

Run: `python3 -m pytest tests/test_diff_reports.py -q`
Expected: all pass.

- [ ] **Step 5: Add wrapper + commit**

`tools/diff_reports.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 -m tools.diff_reports "$@"
```
Then:
```bash
chmod +x tools/diff_reports.sh
git add tools/diff_reports.py tools/diff_reports.sh tests/test_diff_reports.py
git commit -m "feat(tools): run-over-run dir + findings diff helpers"
```

---

### Task 5: Ledger — model, storage, transitions + guardrail

**Files:**
- Create: `tools/ledger.py`
- Test: `tests/test_ledger_core.py`

**Interfaces:**
- Produces:
  - `STATUSES = ("open", "confirmed", "denied", "absorbed", "retired")`
  - `TRANSITIONS: dict[str, set[str]]`
  - `class GuardrailError(Exception)`
  - `@dataclass Correction` with fields: `id, raised, author, target, correction, status, verification="", proof="", resolution="", history=[]`
  - `transition(c: Correction, new_status: str, today: str, proof: str = "") -> Correction`
  - `load_ledger(path: Path) -> list[Correction]`
  - `save_ledger(path: Path, items: list[Correction]) -> None`

- [ ] **Step 1: Write failing tests**

`tests/test_ledger_core.py`:
```python
import pytest
from tools.ledger import (
    Correction, transition, GuardrailError, load_ledger, save_ledger,
)


def _c(**kw):
    base = dict(id="C-001", raised="2026-07-16", author="Reviewer",
                target="Secrets — 'no raw LLM keys'", correction="can read secrets",
                status="open")
    base.update(kw)
    return Correction(**base)


def test_valid_transition_open_to_confirmed():
    c = transition(_c(), "confirmed", "2026-07-17")
    assert c.status == "confirmed"
    assert {"date": "2026-07-17", "status": "confirmed"} in c.history


def test_invalid_transition_rejected():
    with pytest.raises(ValueError):
        transition(_c(status="absorbed"), "open", "2026-07-17")


def test_deny_without_proof_is_blocked():
    with pytest.raises(GuardrailError):
        transition(_c(), "denied", "2026-07-17", proof="")


def test_deny_with_proof_allowed():
    c = transition(_c(), "denied", "2026-07-17", proof="grep shows key IS handled")
    assert c.status == "denied" and c.proof


def test_ledger_roundtrip(tmp_path):
    path = tmp_path / "ledger.jsonl"
    items = [_c(), _c(id="C-002", author="Iris")]
    save_ledger(path, items)
    loaded = load_ledger(path)
    assert [x.id for x in loaded] == ["C-001", "C-002"]
    assert loaded[1].author == "Iris"
```

- [ ] **Step 2: Run — verify fail**

Run: `python3 -m pytest tests/test_ledger_core.py -q`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement `tools/ledger.py` (core)**

```python
"""Corrections & Feedback ledger (cross-run). Canonical store: ledger.jsonl."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

STATUSES = ("open", "confirmed", "denied", "absorbed", "retired")

TRANSITIONS: dict[str, set[str]] = {
    "open": {"confirmed", "denied"},
    "confirmed": {"absorbed"},
    "absorbed": {"retired"},
    "denied": set(),
    "retired": set(),
}


class GuardrailError(Exception):
    """Raised when the LLM tries to `deny` a human correction without proof."""


@dataclass
class Correction:
    id: str
    raised: str
    author: str
    target: str
    correction: str
    status: str
    verification: str = ""
    proof: str = ""
    resolution: str = ""
    history: list[dict] = field(default_factory=list)


def transition(c: Correction, new_status: str, today: str, proof: str = "") -> Correction:
    if new_status not in TRANSITIONS.get(c.status, set()):
        raise ValueError(f"illegal transition {c.status} -> {new_status}")
    if new_status == "denied" and not proof.strip():
        raise GuardrailError(
            "cannot deny a human correction without deterministic proof")
    if new_status == "denied":
        c.proof = proof
    c.status = new_status
    c.history.append({"date": today, "status": new_status})
    return c


def load_ledger(path: Path) -> list[Correction]:
    path = Path(path)
    if not path.exists():
        return []
    items: list[Correction] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            items.append(Correction(**json.loads(line)))
    return items


def save_ledger(path: Path, items: list[Correction]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        "".join(json.dumps(asdict(c), ensure_ascii=False) + "\n" for c in items),
        encoding="utf-8",
    )
```

- [ ] **Step 4: Run — verify pass**

Run: `python3 -m pytest tests/test_ledger_core.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add tools/ledger.py tests/test_ledger_core.py
git commit -m "feat(tools): ledger model, jsonl storage, transitions + anti-gaslighting guardrail"
```

---

### Task 6: Ledger — inbox ingest

**Files:**
- Modify: `tools/ledger.py`
- Test: `tests/test_ledger_ingest.py`

**Interfaces:**
- Consumes: `Correction`, `next_id` (this task), from Task 5.
- Produces:
  - `@dataclass InboxEntry(author: str, target: str, correction: str)`
  - `parse_inbox(text: str) -> list[InboxEntry]`
  - `next_id(existing: list[Correction]) -> str` — `C-NNN`, zero-padded, max+1.
  - `ingest_inbox(inbox_text: str, existing: list[Correction], today: str) -> tuple[list[Correction], str]` — returns `(new_open_corrections, remaining_inbox_text)`; fully-parsed inboxes return `""`.

- [ ] **Step 1: Write failing tests**

`tests/test_ledger_ingest.py`:
```python
from tools.ledger import Correction, parse_inbox, next_id, ingest_inbox

SAMPLE = """- author: Reviewer
  target: Secrets & Token Brokering — "Agents do not handle raw LLM keys"
  correction: The agent has access to the kubeagents-system namespace and can
    read ConfigMaps/Secrets that contain LLM API keys.
"""


def test_parse_inbox_single_entry():
    entries = parse_inbox(SAMPLE)
    assert len(entries) == 1
    e = entries[0]
    assert e.author == "Reviewer"
    assert "Agents do not handle raw LLM keys" in e.target
    assert "read ConfigMaps/Secrets" in e.correction


def test_next_id_increments():
    assert next_id([]) == "C-001"
    assert next_id([Correction("C-004", "d", "a", "t", "c", "open")]) == "C-005"


def test_ingest_creates_open_and_clears_inbox():
    new, remaining = ingest_inbox(SAMPLE, [], "2026-07-16")
    assert len(new) == 1
    assert new[0].status == "open"
    assert new[0].id == "C-001"
    assert new[0].raised == "2026-07-16"
    assert remaining.strip() == ""
```

- [ ] **Step 2: Run — verify fail**

Run: `python3 -m pytest tests/test_ledger_ingest.py -q`
Expected: FAIL (`ImportError: cannot import name 'parse_inbox'`).

- [ ] **Step 3: Extend `tools/ledger.py`**

Add these imports/definitions to `tools/ledger.py`:
```python
import re

_ID_RE = re.compile(r"C-(\d+)")


@dataclass
class InboxEntry:
    author: str
    target: str
    correction: str


def parse_inbox(text: str) -> list[InboxEntry]:
    entries: list[InboxEntry] = []
    cur: dict[str, str] | None = None
    key: str | None = None
    for raw in text.splitlines():
        m = re.match(r"-\s+author:\s*(.*)$", raw)
        if m:
            if cur:
                entries.append(_finish_entry(cur))
            cur = {"author": m.group(1).strip(), "target": "", "correction": ""}
            key = "author"
            continue
        if cur is None:
            continue
        m = re.match(r"\s+(target|correction):\s*(.*)$", raw)
        if m:
            key = m.group(1)
            cur[key] = m.group(2).strip()
        elif raw.strip() and key in ("target", "correction"):
            cur[key] = (cur[key] + " " + raw.strip()).strip()
    if cur:
        entries.append(_finish_entry(cur))
    return entries


def _finish_entry(cur: dict[str, str]) -> InboxEntry:
    return InboxEntry(cur["author"], cur["target"], cur["correction"])


def next_id(existing: list[Correction]) -> str:
    nums = [int(m.group(1)) for c in existing if (m := _ID_RE.fullmatch(c.id))]
    return f"C-{(max(nums) + 1) if nums else 1:03d}"


def ingest_inbox(inbox_text: str, existing: list[Correction],
                 today: str) -> tuple[list[Correction], str]:
    new: list[Correction] = []
    pool = list(existing)
    for entry in parse_inbox(inbox_text):
        cid = next_id(pool)
        c = Correction(id=cid, raised=today, author=entry.author,
                       target=entry.target, correction=entry.correction,
                       status="open", history=[{"date": today, "status": "open"}])
        new.append(c)
        pool.append(c)
    return new, ""
```

- [ ] **Step 4: Run — verify pass**

Run: `python3 -m pytest tests/test_ledger_ingest.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add tools/ledger.py tests/test_ledger_ingest.py
git commit -m "feat(tools): parse corrections/inbox.md and ingest as Open ledger entries"
```

---

### Task 7: Ledger — markdown rendering

**Files:**
- Modify: `tools/ledger.py`
- Test: `tests/test_ledger_render.py`

**Interfaces:**
- Consumes: `Correction` from Task 5.
- Produces:
  - `render_markdown(items: list[Correction], active_only: bool = True) -> str` — active view excludes `retired` (archived); `denied` entries render under a "Documented false-positives" subsection.

- [ ] **Step 1: Write failing tests**

`tests/test_ledger_render.py`:
```python
from tools.ledger import Correction, render_markdown


def _c(status, cid="C-001", author="Reviewer"):
    return Correction(cid, "2026-07-16", author, "Secrets — 'x'", "claim", status)


def test_render_includes_active_entry():
    md = render_markdown([_c("open")])
    assert "C-001" in md and "Reviewer" in md and "open" in md.lower()


def test_active_only_excludes_retired():
    md = render_markdown([_c("retired")], active_only=True)
    assert "C-001" not in md


def test_denied_rendered_as_false_positive():
    md = render_markdown([_c("denied")])
    assert "false-positive" in md.lower()
    assert "C-001" in md
```

- [ ] **Step 2: Run — verify fail**

Run: `python3 -m pytest tests/test_ledger_render.py -q`
Expected: FAIL (`ImportError: cannot import name 'render_markdown'`).

- [ ] **Step 3: Extend `tools/ledger.py`**

Add to `tools/ledger.py`:
```python
def render_markdown(items: list[Correction], active_only: bool = True) -> str:
    active = [c for c in items if c.status in ("open", "confirmed", "absorbed")]
    denied = [c for c in items if c.status == "denied"]
    archived = [c for c in items if c.status == "retired"]

    out = ["# Corrections & Feedback", ""]
    out.append("## Active")
    out.append("")
    for c in active:
        out.append(_render_entry(c))
    if denied:
        out += ["", "## Documented false-positives", ""]
        for c in denied:
            out.append(_render_entry(c))
    if not active_only and archived:
        out += ["", "## Retired (archived)", ""]
        for c in archived:
            out.append(_render_entry(c))
    return "\n".join(out) + "\n"


def _render_entry(c: Correction) -> str:
    parts = [
        f"### {c.id} — {c.status} (raised {c.raised} by {c.author})",
        f"- **Target:** {c.target}",
        f"- **Correction:** {c.correction}",
    ]
    if c.verification:
        parts.append(f"- **Verification:** {c.verification}")
    if c.proof:
        parts.append(f"- **Proof:** {c.proof}")
    if c.resolution:
        parts.append(f"- **Resolution:** {c.resolution}")
    return "\n".join(parts) + "\n"
```

- [ ] **Step 4: Run — verify pass**

Run: `python3 -m pytest tests/test_ledger_render.py -q`
Expected: all pass.

- [ ] **Step 5: Full-suite green + commit**

Run: `python3 -m pytest -q`
Expected: all tests across all files pass.

```bash
git add tools/ledger.py tests/test_ledger_render.py
git commit -m "feat(tools): render corrections ledger to markdown (active/false-positive/archived)"
```

---

## Self-Review

**Spec coverage (Plan 1 scope):**
- Pre-flight drift (spec §4 Step 0) → Task 2. ✓
- `audit_state.json` schema/validator (§4 Phase 1) → Task 3. ✓
- Deterministic What's-Changed diff (§6, Iris #3) → Task 4. ✓
- Ledger storage + lifecycle + anti-gaslighting guardrail (§5.3/5.4) → Task 5. ✓
- Inbox → ledger ingest (§5.2/5.5) → Task 6. ✓
- Ledger snapshot render / Tab 12 (§5.1) → Task 7. ✓
- *Out of Plan-1 scope (→ Plan 2):* SKILL.md rewrite, 13 tab templates, `toc.md`/`note.md`, `generate.sh` wiring, and the actual per-run *orchestration* that calls these tools and performs LLM verification/absorption.

**Type consistency:** `Correction` fields and `transition`/`ingest_inbox`/`render_markdown`/`load_ledger`/`save_ledger` signatures are identical across Tasks 5–7. `diff_findings` keys (`added/removed/changed`) match the test. `Check`/`CheckResult`/`PreflightResult` consistent in Task 2.

**Placeholder scan:** every code step contains complete, runnable code; every run step states the exact command and expected result.
