# Audit v2 — SKILL Rework & Tab Templates — Implementation Plan (Plan 2 of 2)

> **⚠️ DRAFT / IN PROGRESS.** The decomposition, file structure, interfaces, and
> the Plan-1 tool signatures below are locked. The per-task **TDD step bodies
> (failing test → impl → commit) are not yet written** for Tasks 2–6. A fresh
> session should: (1) re-read the spec §3.2 (tab outlines) and §4 (SKILL rework),
> (2) flesh each task's steps following Plan 1's style, (3) then execute via
> subagent-driven-development. **Resume at Task 1.**

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:writing-plans to finish
> the step bodies, then superpowers:subagent-driven-development to execute.

**Goal:** Turn Plan 1's foundation tooling into a running v2 audit — a reworked
`SKILL.md` (two-phase, drift-resistant), the 13 tab section templates, corrections
+ What's-Changed drivers, and rewired `generate.sh`/`toc.md`.

**Architecture:** The SKILL orchestrates: Step 0 mechanical pre-flight → Phase 1
inspect the kube-agents repo and export `audit_state.json` (validated) → Phase 2
render the 13 tabs from that JSON (+ corrections processing + What's-Changed) →
Step 3 publish via `generate.sh`. Prose/authoring lives in `SKILL.md` and
`templates/`; the mechanical glue (corrections, diff assembly) is stdlib Python
CLIs wrapping Plan 1's `tools/`.

**Tech Stack:** Python 3 stdlib (extends `tools/`), bash (`generate.sh`), Markdown
(SKILL + templates), `pytest` (dev-only).

## Global Constraints

- Runtime deps: Python 3 standard library only; `pytest` dev-only. (Same as Plan 1.)
- Report is **13 tabs across 6 domains**; Threat Model is the spine and the SOLE
  home of the Default-GitOps-vs-Read-Only-Advisor stance contrast (spec §3).
- SKILL inspection is **hybrid intent + dated path-hints** (`as of 2026-07-16 —
  verify`); every run re-grounds and runs the mechanical Step-0 pre-flight first
  (spec §4).
- Single `platform` agent; install namespace `kubeagents-system`; dates `YYYY-MM-DD` UTC.
- Corrections intake is the structured `corrections/inbox.md` ONLY (no gdoc scraping — spec §2/§8).
- Ledger canonical store `corrections/ledger.jsonl`; `ledger.md` + Tab 12 are rendered views.
- `generate.sh` onedoc path is `${ONEDOC_BIN:-onedoc}` (already scrubbed).

## Plan-1 tool interfaces (consume, do not reimplement)

```
tools/preflight.py:   run_preflight(base: Path, checks: list[Check]) -> PreflightResult
                      DEFAULT_CHECKS; Check(kind,target,reason,optional); PreflightResult.ok / .report_md()
                      CLI: python3 -m tools.preflight   (env KUBE_AGENTS_DIR; exit 1 on drift)
tools/validate_state: validate_state(data: dict) -> list[str];  load_and_validate(path) -> list[str]
                      CLI: python3 -m tools.validate_state <audit_state.json>   (exit 1 on errors)
tools/diff_reports:   diff_dirs(old: Path, new: Path) -> str;  diff_findings(old,new) -> {added,removed,changed}
                      CLI: python3 -m tools.diff_reports <old_dir> <new_dir>
tools/ledger.py:      Correction(id,raised,author,target,correction,status,verification,proof,resolution,history)
                      transition(c,new_status,today,proof="") -> Correction  (denied requires proof)
                      parse_inbox(text) -> list[InboxEntry(author,target,correction)]
                      next_id(existing) -> "C-NNN";  ingest_inbox(text,existing,today) -> (list[Correction], remaining_str)
                      load_ledger(path)/save_ledger(path,items);  render_markdown(items, active_only=True) -> str
                      STATUSES; TRANSITIONS; GuardrailError    (NO CLI — Plan 2 Task 1 adds one)
```

## File Structure

- `tools/process_corrections.py` (+`.sh`) — NEW. CLI that: loads `corrections/ledger.jsonl`,
  ingests `corrections/inbox.md` as `open` entries, **surfaces any unparsed inbox content**
  (final-review finding D — human corrections must not be silently dropped), saves the ledger,
  clears the inbox, and renders the Corrections tab (`<date>/corrections_feedback.md`).
- `tools/whats_changed.py` (+`.sh`) — NEW. Assembles the deterministic diff inputs
  (`diff_dirs` on the two dated dirs + `diff_findings` on the two `audit_state.json`) into a
  structured artifact the SKILL curates into `<date>/whats_changed.md`.
- `templates/` — NEW. 13 tab section-outline templates (one per tab, spec §3.2), each a
  Markdown skeleton of required headings the agent fills in Phase 2.
- `generate-security-analysis-report/SKILL.md` — REWRITE to the two-phase orchestration (spec §4).
- `generate.sh` — MODIFY: replace the 6-tab `create_tab` list with the 13-tab list (new order/filenames);
  add a pre-publish gate that runs `tools.preflight` and `tools.validate_state` and aborts on failure.
- `toc.md`, `note.md` — MODIFY to the 13-tab list.
- `tests/test_process_corrections.py`, `tests/test_whats_changed.py` — NEW.

## Tasks

> Tasks 1–2 are TDD Python (flesh like Plan 1). Task 3 is template authoring
> (verify by presence + required-heading check). Tasks 4–6 are authoring/wiring
> (verify by dry-run + shell sanity). Draw final task boundaries when fleshing.

### Task 1 — `tools/process_corrections.py` (corrections driver + unparsed-inbox guard)  [TDD]
**Files:** Create `tools/process_corrections.py`, `tools/process_corrections.sh`; Test `tests/test_process_corrections.py`.
**Consumes:** `ledger.load_ledger/save_ledger/ingest_inbox/render_markdown`, `ledger.parse_inbox`.
**Produces:**
- `find_unparsed(inbox_text: str) -> list[str]` — non-blank inbox lines not consumed by any parsed
  entry (guards finding D). Define "consumed" precisely when fleshing (recognized keys `- author:`,
  `  target:`, `  correction:`, and indented `correction:` continuations).
- `process(inbox_text, ledger_items, today) -> ProcessResult(new_items, corrections_md, unparsed)`.
- CLI `python3 -m tools.process_corrections` (env: `ANALYSIS_DIR`, date arg): loads ledger + inbox,
  runs `process`, writes ledger.jsonl, clears inbox, writes `<date>/corrections_feedback.md`;
  **exits non-zero (or prints a loud warning) if `unparsed` is non-empty** so no human comment is lost.
**Steps:** _(to flesh — TDD: test find_unparsed on clean + malformed inbox; test process creates Open
entries + renders tab + reports unparsed; test CLI round-trip on tmp dirs.)_

### Task 2 — `tools/whats_changed.py` (deterministic diff assembler)  [TDD]
**Files:** Create `tools/whats_changed.py`, `tools/whats_changed.sh`; Test `tests/test_whats_changed.py`.
**Consumes:** `diff_reports.diff_dirs`, `diff_reports.diff_findings`.
**Produces:** `assemble(prev_dir, cur_dir) -> dict` (structured deltas: dir diff text + findings
added/removed/changed + prev/cur dates) that the SKILL renders into `whats_changed.md`. Finds the
previous dated run (latest date dir < today) — add `previous_run_dir(analysis_dir, today) -> Path|None`.
**Steps:** _(to flesh — TDD: previous_run_dir picks the right dir / None when first run; assemble on two
fixture dirs incl. audit_state.json.)_

### Task 3 — 13 tab section templates  [authoring]
**Files:** Create `templates/<tab>.md` × 13 (names per spec §3 filename column).
Each carries the fixed section headings from spec §3.2 (e.g. Threat Model: component overview, entry
points, trust boundaries, sensitive data paths, **Privileged Actions Matrix (Default vs Read-Only)**,
out-of-scope, priority review areas → links to domain tabs). Encode the two structural rules: Threat
Model is the spine; stance contrast lives ONLY there.
**Verify:** all 13 present; each has its required headings (a simple presence/heading check — the
deferred structural linter, spec §8, can formalize this later).

### Task 4 — Rewire `generate.sh` + `toc.md`/`note.md`  [wiring]
**Files:** Modify `generate.sh`, `toc.md`, `note.md`.
Replace the 6 `create_tab` calls with the 13-tab list in order (Tab 0 What's Changed … Tab 12
Corrections). Add a pre-publish gate: run `python3 -m tools.preflight` (KUBE_AGENTS_DIR) and
`python3 -m tools.validate_state <date>/audit_state.json`; abort publish on non-zero. Update `toc.md`
and `note.md` tab lists to the 13 tabs.
**Verify:** `bash -n generate.sh`; dry-run with `ONEDOC_BIN=true` (no-op) over a fixture dated dir.

### Task 5 — Rewrite `SKILL.md` to two-phase orchestration  [authoring]
**Files:** Rewrite `generate-security-analysis-report/SKILL.md` per spec §4:
Step 0 pre-flight (call `tools.preflight`, abort on drift, record drift into whats_changed); Phase 1
inspection intents (hybrid intent + dated hints; drop YOLO/agent-system/multi-agent; add agentic,
runtime, pipeline, data/detection intents) → write & validate `audit_state.json`; Phase 2 render the 13
tabs from audit_state.json + templates, run `tools.process_corrections`, run `tools.whats_changed`;
Step 3 `generate.sh`. Update frontmatter description (13 files, single-agent).
**Verify:** self-consistency review against spec §4; no stale v1 references (grep for `agent-system`,
`YOLO_PERMISSIONS`, `devteam`, "6 markdown").

### Task 6 — End-to-end dry run + docs  [integration]
**Files:** maybe `tests/` smoke or a documented manual dry-run; update `README.md` status section
(v2 now runnable). Run the whole pipeline against a fixture kube-agents checkout with `ONEDOC_BIN=true`;
confirm 13 tab files produced, audit_state.json validates, corrections + whats_changed generate, no
unparsed-inbox loss.

## Resume checklist (for the next session)
1. `git -C ../kube-agents-security-analysis log --oneline -3` — confirm state; branch off `main`.
2. Re-read spec §3.2 and §4 (`docs/specs/2026-07-16-audit-framework-design.md`).
3. Flesh Task 1 TDD steps first (it's the most concrete + closes finding D), then 2, then author 3–6.
4. Execute via subagent-driven-development (implementer=haiku for TDD-with-code, sonnet reviewers,
   opus final review), same as Plan 1 (see `.superpowers/sdd/progress.md` from Plan 1 for the pattern).
