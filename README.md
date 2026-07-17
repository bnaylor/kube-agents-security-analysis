# kube-agents-security-analysis

A **repeatable, structured security audit** of the [`kube-agents`](https://github.com/gke-labs/kube-agents)
codebase. Each run produces a set of date-stamped Markdown analyses that are
compiled into a tabbed Google Doc for human review, so posture can be tracked
and diffed over time rather than re-derived from scratch.

> **Status: v2 wired, pending a live end-to-end run.** The structured
> **6-domain / 13-tab framework** (corrections feedback loop + drift resistance)
> is built: the `tools/` package, the 11 tab templates in `templates/`, the
> two-phase `SKILL.md`, and the rewired `generate.sh`/`toc.md` (46 passing
> tests). The one thing not yet exercised is a **live agent run** producing a
> real `audit_state.json` + filled tabs and a Google Doc (needs the agent
> runtime and the `onedoc` binary). The mechanical spine — pre-flight, the
> corrections and What's-Changed tools — is smoke-tested against the real
> `kube-agents` checkout. The `2026-07-15/` directory is the historical v1 run.
>
> Known follow-up: `tools/preflight.py`'s optional `command` checks (e.g.
> `kubectl get ns`) have no subprocess timeout, so they can stall when kubectl
> is installed but no cluster is reachable — add a `timeout=` to the command check.

## What's here

| Path | What it is |
|------|-----------|
| `docs/specs/2026-07-16-audit-framework-design.md` | The approved v2 framework design (domains, tabs, corrections ledger, drift resistance). Start here. |
| `docs/specs/plans/2026-07-16-audit-foundation-tooling.md` | The implementation plan for the tooling below. |
| `tools/` | Stdlib-only Python tools the v2 audit orchestrates (see [Tooling](#tooling)). |
| `tests/` | `pytest` suite for `tools/` (dev-only dependency). |
| `schemas/audit_state.schema.json` | Shape of the `audit_state.json` ground-truth artifact a run produces. |
| `generate-security-analysis-report/SKILL.md` | The v1 audit skill (Gemini-era; being reworked in Plan 2). |
| `run_security_analysis.sh`, `generate.sh` | v1 pipeline: launch the skill, then compile the Markdown into a Google Doc. |
| `2026-07-15/` | The first (v1) report run, kept as a historical baseline. |
| `docs/reviews/` | Peer reviews of the design spec. |

## How it works

1. An agent runs the audit skill against a checkout of `kube-agents`, inspecting
   RBAC/IAM, admission webhooks, token brokering, the agentic attack surface
   (prompt injection, MCP/tools, skills & autonomy), runtime hardening, the
   GitOps/CI pipeline, and audit/detection.
2. It writes one Markdown file per report tab into a dated directory
   (`<ANALYSIS_DIR>/YYYY-MM-DD/`).
3. `generate.sh` compiles those Markdown files into a tabbed Google Doc.

The v2 design adds a mechanical pre-flight drift check, a two-phase
`inspect → audit_state.json → render` execution model, a cross-run corrections
ledger, and a run-over-run "What's Changed" summary.

## Configuration

All scripts honor these environment variables:

| Variable | Default | Meaning |
|----------|---------|---------|
| `SRC_DIR` | `$HOME/src` | Base dir for the two repos below. |
| `KUBE_AGENTS_DIR` | `$SRC_DIR/kube-agents` | The `kube-agents` checkout being audited. |
| `ANALYSIS_DIR` | `$SRC_DIR/kube-agents-security-analysis` | Where dated report dirs are written (this repo). |

## Running a report (v1 pipeline)

```bash
# Run for today's date (or pass a specific YYYY-MM-DD)
./run_security_analysis.sh
./run_security_analysis.sh 2026-07-15

# Point at a repo / output location elsewhere
SRC_DIR=/path/to/src KUBE_AGENTS_DIR=/path/to/kube-agents ./run_security_analysis.sh
```

`run_security_analysis.sh` launches the audit skill (via `agentapi` if present,
otherwise it prints the prompt to run in your agent session). Once the Markdown
files exist, `generate.sh <date>` builds the Google Doc.

**External dependencies:** `generate.sh` shells out to an `onedoc` binary to
create the Google Doc — set `ONEDOC_BIN` to its path (defaults to `onedoc` on
`PATH`) — and `run_security_analysis.sh` uses `agentapi` to launch the agent.
Both are optional to the tooling below — you can produce and read the Markdown
reports without them.

## Tooling

Stdlib-only Python (no runtime third-party deps). Modules live in the `tools/`
package; run them from the repo root.

```bash
# Pre-flight: fail loudly if the audited repo's expected paths have drifted
KUBE_AGENTS_DIR=/path/to/kube-agents python3 -m tools.preflight   # exit 1 on drift
./tools/preflight.sh                                              # thin wrapper

# Validate a run's ground-truth artifact
python3 -m tools.validate_state path/to/audit_state.json          # exit 1 on errors

# Diff two dated report directories (feeds the "What's Changed" tab)
python3 -m tools.diff_reports 2026-07-15 2026-07-16
./tools/diff_reports.sh 2026-07-15 2026-07-16
```

`tools/ledger.py` is the cross-run **corrections ledger** (imported by the audit
skill, no CLI): it ingests reviewer comments from `corrections/inbox.md` into a
tracked `corrections/ledger.jsonl`, moves each through a lifecycle
(`open → confirmed | denied → absorbed → retired`), and renders the Corrections
tab. It enforces an **anti-gaslighting guardrail** — a correction can only be
marked `denied` with deterministic tool-output proof, so the agent can't dismiss
a human's feedback on its own reasoning.

## Development

```bash
python3 -m pip install -r requirements-dev.txt   # pytest
python3 -m pytest -q                             # run the suite
```
