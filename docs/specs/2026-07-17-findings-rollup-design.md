# Findings Rollup Tab — Design

**Date:** 2026-07-17
**Author:** Brian Naylor (with Claude Code)
**Status:** Approved design, pending implementation plan

## 1. Context & Motivation

A run's `audit_state.json` already carries every finding as structured data
(`id, tab, statement, severity, evidence, tracking`) — the 2026-07-16 run has 71.
But they're scattered across 11 domain tabs, so there's no single "here are all
the bugs" view. We want a **Findings** tab: one severity-sorted list where each
finding has a grabbable ID, so a team can pick one up at sprint planning and go.

## 2. Decisions (locked)

- **Permanent framework tab.** A new `tools/findings_rollup.py` renders
  `audit_state.json` → `findings.md`; it's added to the `tabs.py` manifest so it
  appears in every run (HTML report *and* Google Doc), and wired into the SKILL's
  Phase 2.
- **Position: second tab**, immediately after "What's Changed".
- **Info split.** `Info`-severity findings are observations, not bugs — shown in a
  separate "Informational" section so nobody grabs a non-action item.

## 3. Goals / Non-Goals

**Goals**
- One `findings.md` tab: a summary line + a severity-sorted action-item table with
  a grabbable ID per row, plus a separated informational list.
- Generated deterministically from `audit_state.json`; a first-class tab everywhere.

**Non-Goals**
- Auto-creating GitHub issues per finding (the `tracking` column just shows the
  link/`UNTRACKED`).
- Any interactive filtering/sorting UI (it's static markdown → HTML/gdoc).

## 4. Architecture & Files

- **`tools/findings_rollup.py`** (new):
  - `SEVERITY_ORDER: dict[str, int]` — `Critical < High < Medium < Low < Info`
    (unknown severities sort after known, before Info's trailing block).
  - `render_findings(findings: list[dict]) -> str` — the `findings.md` markdown.
  - `main(argv)` — read `<analysis_dir>/<date>/audit_state.json`, write
    `<...>/findings.md`. CLI `python3 -m tools.findings_rollup <date> [analysis_dir]`.
    Missing/invalid `audit_state.json` → write a `findings.md` with a
    "no findings data for this run" note (exit 0; not fatal).
- **`tools/findings_rollup.sh`** (new): thin wrapper.
- **`tools/tabs.py`** (modify): insert `("findings.md", "Findings")` at index 1
  (after `whats_changed.md`). Manifest becomes 14 entries.
- **SKILL** (`generate-security-analysis-report/SKILL.md`, modify): add a Phase-2
  step running `python3 -m tools.findings_rollup <date> <analysis_dir>`.
- **`tests/test_findings_rollup.py`** (new); **`tests/test_tabs.py`** (modify to 14).

## 5. `findings.md` Layout

```
# Findings

**71 findings** — 10 Critical · 21 High · 22 Medium · 5 Low · 13 Info

Grab one by **ID** at sprint planning.

## Action items

| ID | Severity | Domain | Finding | Evidence | Tracking |
|----|----------|--------|---------|----------|----------|
| SEC-003 | Critical | Secrets & Token Brokering | … statement … | role.yaml:42 | UNTRACKED |
| …one row per Critical/High/Medium/Low finding, severity-sorted… |

## Informational

| ID | Domain | Note |
|----|--------|------|
| ARCH-001 | Architectural & Security Summary | … statement … |
```

- **Summary line:** total + per-severity counts (only nonzero severities shown).
- **Action items:** all findings whose severity is not `Info`, sorted by
  `SEVERITY_ORDER` then by `id`. Columns: `ID | Severity | Domain | Finding |
  Evidence | Tracking`.
- **Informational:** the `Info` findings, `ID | Domain | Note`.
- **Domain** is the human title: map the finding's `tab` (e.g.
  `architectural_summary`) to its manifest title via `tabs.TABS` (`<tab>.md` →
  title); fall back to the raw `tab` value if unmapped.
- Table-cell text has `|` escaped as `\|` and newlines collapsed to spaces so a
  multi-line `statement` stays one table row.

## 6. Edge Cases

- No `audit_state.json` / invalid JSON / not a dict → `findings.md` = a short
  note; do not crash.
- `findings` empty → summary "0 findings" + a "no findings recorded" note.
- Unknown severity string → treated as an action item, sorted after known
  severities (rank between Low and Info via the order map's default).
- `tab` not in the manifest → show the raw `tab` string as the domain.

## 7. Testing (pytest)

- `render_findings`: severity sort (a Critical row precedes a High/Medium/Low
  row); summary counts correct; `Info` findings land in the Informational section,
  not Action items; a `|`/newline in a statement is escaped/collapsed (still one
  row); domain title mapping works and falls back for an unknown tab.
- `main` (tmp dir): with a small `audit_state.json` writes `findings.md`
  containing the expected rows; missing `audit_state.json` writes the note (exit 0).
- `tabs.py`: manifest is now 14 entries; `("findings.md", "Findings")` is at
  index 1; first entry still `whats_changed.md`, last still `corrections_feedback.md`.

## 8. Rollout for tonight

After implementation, run `python3 -m tools.findings_rollup 2026-07-16 .` and
regenerate `2026-07-16/report.html`, so the Findings tab is present for the 9am
meeting.
