# Snapshot-only report — drop cross-run tracking

**Date:** 2026-07-17
**Status:** Approved (design)
**Supersedes:** the `tracking` field of `audit_state.json` and the ID-keyed
findings diff introduced in `2026-07-16-audit-framework-design.md`.

## Problem

The **Findings** tab has a `Tracking` column, and every finding in
`audit_state.json` carries a `tracking` field (schema-required). It is
**non-functional**: agents author the JSON, but nothing feeds them a "this
finding is tracked at #NNN" signal, so every finding is written `UNTRACKED`
(all 71 in the 2026-07-16 run). There is no input surface where a human who
grabs a finding at sprint planning can record that fact and have it appear in
the column. The column is a promise with no backing store.

Investigating a fix surfaced a deeper issue: **finding IDs are not stable across
runs.** They are `<TAB>-NNN`, assigned in whatever order the agent lists
findings that run. `MCP-001` means "first finding under the MCP tab this run,"
nothing durable. Yet `tools/diff_reports.py:diff_findings` matches runs *purely*
by `f["id"]` — so the "What's Changed" findings diff is already standing on sand:
if the agent renumbers between runs (nothing stops it), every finding reports as
both removed and re-added.

So the tracking column and the What's-Changed diff depend on the same missing
primitive — **stable finding identity across regeneration** — which is genuinely
hard (line numbers move exactly when a finding is being fixed; the agent rewords
statements run to run).

## Decision

**Do not build cross-run identity or tracking.** Make the standalone report a
pure **snapshot**: it answers exactly one question — *what is true in the code at
this sha, today.* No memory across runs.

Rationale (YAGNI, reinforced by roadmap):
- The near-term use is a ~2-week blitz where humans + agents burn the findings
  list down. Real tracking lives in existing bug tools during the blitz.
- The long-term direction is to bundle this capability **into kube-agents as a
  service that files PRs against the issues it finds.** In that world, identity
  and tracking are native and free — *the PR is the finding*: its number is the
  ID, its state is the lifecycle, its diff is native. Any bespoke
  tracking/anchor/resolver machinery built now is interim scaffolding we would
  rip out the moment the service exists.
- Keeping the report offline/stdlib-only (no live GitHub read at audit time) is
  worth preserving.

Finding IDs stay `<TAB>-NNN` but are **explicitly per-run ephemeral** — a handle
to point at a row in *this* report/meeting, valid only within this run.

**Non-goals / future (not designed here):** an agent that autonomously files PRs
against security findings is its own autonomy/security design (human-gate
boundaries, allowed scope, provenance). It slots into the existing audit domains
as future work; it is not in scope now.

## Changes (all subtraction / simplification)

Load-bearing:

1. **`schemas/audit_state.schema.json`** — remove `tracking` from the finding
   `required` list and `properties`.
2. **`tools/validate_state.py`** — remove `tracking: str` from `FINDING_REQUIRED`.
3. **`tools/findings_rollup.py`** — remove the `Tracking` column from the
   Action-items table header, separator, and rows. (Informational table is
   already tracking-free.)
4. **`tools/whats_changed.py`** — replace the `diff_findings`-based `assemble`
   with a **count-based summary** that needs no identity:
   ```
   {
     "previous": <date>, "current": <date>,
     "previous_ref": <kube_agents_ref or null>, "current_ref": <... or null>,
     "previous_count": M, "current_count": N,
     "previous_by_severity": {sev: n, ...}, "current_by_severity": {sev: n, ...}
   }
   ```
   Stop importing/calling `diff_dirs` and `diff_findings`. First-run behavior
   (no prior report → "first run" note) is unchanged.
5. **Retire `tools/diff_reports.py`** (`diff_dirs` + `diff_findings`),
   `tools/diff_reports.sh`, and `tests/test_diff_reports.py`. Nothing else
   imports the module once `whats_changed` stops; both functions encode the now
   -invalid assumptions (diff-by-ephemeral-id, diff-of-reworded-prose-tabs).
6. **`generate-security-analysis-report/SKILL.md`**
   - Phase 1: drop `tracking` from the `audit_state.json` field list and the
     inspection intents; add one line that finding IDs are **per-run ephemeral**
     (valid only within this report; not a cross-run handle).
   - Step 2b (What's Changed): describe the prose note the agent writes from the
     count summary (e.g. *"Re-audited at `abc123` (was `def456`); 61 findings,
     down from 82 — Critical 8→6, High 19→15."*) instead of a per-finding diff.
7. **Templates** — reword the two soft prose references to an "owner/tracking
   link": `templates/agentic_tools_mcp_trust.md:13`,
   `templates/threat_model.md:20`.

Docs:

8. **README** — check for and update any tracking-column / What's-Changed-diff
   description; add a one-line note that the report is a snapshot (tracking is
   external now, native to the future kube-agents service).
9. This design doc records the rationale so a tracking column is not re-added
   casually.

Explicitly **not** changed:

- The committed `2026-07-16/` run keeps `tracking: UNTRACKED` on its findings —
  a frozen historical artifact; we do not rewrite a superseded run.

## Data flow (after)

```
Phase 1: agent inspects code @ sha → audit_state.json
         (findings: id, tab, statement, severity, evidence — NO tracking;
          ids are per-run ephemeral)
Phase 2: findings_rollup  → findings.md  (Action-items table, no Tracking col)
         whats_changed     → count summary → agent-curated prose whats_changed.md
Step 3 : generate.sh / html_report → snapshot report
```

No cross-run identity anywhere. Tracking happens in external bug tools now, and
natively (PRs) once this is a kube-agents service.

## Testing

Stay offline / stdlib. Update:

- `tests/test_validate_state.py` — a finding without `tracking` is valid; drop
  any "missing tracking" expectation.
- `tests/test_findings_rollup.py` — Action-items table has no `Tracking` column;
  assert the header/columns explicitly.
- `tests/test_whats_changed.py` — `assemble` returns the count summary
  (previous/current counts + by-severity + refs); no `dir_diff`/`findings` keys;
  first-run note preserved.
- Delete `tests/test_diff_reports.py`.

Full suite green after the subtraction.

## Risks

- **Losing a mechanical What's-Changed diff.** Accepted: in a blitz the burndown
  is better answered by the external bug tracker; the count summary is honest and
  cheap. If per-finding cross-run diffing is ever truly needed, it belongs in the
  future service where PR numbers give real identity — not bolted on here.
- **Ephemeral IDs confusing a reader** who expects `MCP-001` to be durable.
  Mitigated by stating it plainly in the report/SKILL.
