---
name: generate-security-analysis-report
description: Runs a repeatable, structured security audit of the kube-agents repository — a mechanical drift pre-flight, then a two-phase inspect→audit_state.json→render pass that produces 14 date-stamped Markdown tabs (6 domains + What's Changed + Findings + Corrections), processes reviewer corrections, and compiles a tabbed Google Doc.
---

# Task

Produce the v2 kube-agents security report for a target date. The report is
**14 tabs across 6 domains** plus a run-over-run "What's Changed" summary and a
cross-run Corrections ledger. Design and rationale live in
`docs/specs/2026-07-16-audit-framework-design.md` — read it if intent is unclear.

Execution is **two-phase**: inspect the repo once and export a single
ground-truth `audit_state.json`, then render every tab from that JSON. This keeps
the 14 tabs mutually consistent and keeps the diffing deterministic.

Inspection is **hybrid intent + dated path-hints**: each step says *what to find*
first, then lists today's known paths marked `as of 2026-07-16 — verify`. Re-ground
every run; do not trust a hint that no longer resolves.

---

# Step 0 — Pre-flight verification (mechanical, hard-fail)

Before any analysis, confirm the audited repo hasn't drifted out from under the
dated hints:

```
cd "${ANALYSIS_DIR}" && KUBE_AGENTS_DIR="${KUBE_AGENTS_DIR}" python3 -m tools.preflight
```

If it exits non-zero, **stop**: record the drift report as the first item in this
run's What's Changed tab and reconcile the hints/inspection steps before continuing.
Drift is a hard failure, not a warning.

Resolve paths first:
- `SRC_DIR="${SRC_DIR:-$HOME/src}"`
- `KUBE_AGENTS_DIR="${KUBE_AGENTS_DIR:-$SRC_DIR/kube-agents}"`
- `ANALYSIS_DIR="${ANALYSIS_DIR:-$SRC_DIR/kube-agents-security-analysis}"`
- Target UTC date `YYYY-MM-DD`; ensure `${ANALYSIS_DIR}/<date>/` exists.

---

# Phase 1 — Inspection & state export (→ `audit_state.json`)

Inspect `${KUBE_AGENTS_DIR}` and write ONE structured ground-truth artifact,
`${ANALYSIS_DIR}/<date>/audit_state.json`, conforming to
`schemas/audit_state.schema.json` (top-level: `generated_at`, `kube_agents_ref`
(git sha), `install_namespace`, `agents`, `findings[]` where each finding has
`id, tab, statement, severity, evidence` (`file:line`), `tracking` (kube-agents
issue/PR or `UNTRACKED`)). Then validate it:

```
cd "${ANALYSIS_DIR}" && python3 -m tools.validate_state "<date>/audit_state.json"
```

## Inspection intents (what to find → hints as of 2026-07-16, verify)

- **Agent model** — confirm the active agent set (expect single `platform`;
  operator/devteam removed #256). Hint: `agents/`, `agents/platform/config.yaml`.
- **Custom resources & controller RBAC** — `k8s-operator/api/v1alpha1/`,
  `k8s-operator/internal/controller/` (ClusterRole/Binding the operator generates).
- **GCP IAM** — roles granted to the platform GSA. Hint:
  `k8s-operator/scripts/provision_03_gcp_iam.sh` (resolve current path).
- **Secrets / token brokering** — Minty/KMS/OIDC-CEL/0600. Hint:
  `agents/platform/scripts/github_token_refresh.py`, `integrations/github/`.
- **Untrusted input (agentic)** — enumerate sources reaching the LLM context;
  the **K8s API is the primary indirect-injection vector**: pod logs/stdout,
  labels, annotations, CRD specs, events; plus GitHub issues/PRs and chat.
- **Tools / MCP / inter-agent** — MCP servers & tool scopes; `call_agent` and the
  `API_SERVER_KEY: "none"` fallback (`agents/platform/scripts/agent_common_server.py`).
- **Skills & autonomy** — skill provenance (`sync-upstream-skills`), in-pod script
  execution, cron autonomy & human-gate boundaries.
- **Admission** — the single `platformagent_webhook.go` (cardinality, GCS lock).
- **Runtime** — gVisor runtimeClass, SecurityContext, NetworkPolicy egress.
- **Pipeline** — GitOps `submit-suggestion` flow, branch protection, auto-merge,
  CI injection; the read-only SRE agent write-channel (kube-agents PR #315);
  Actions/prow (zizmor); image/dep pins.
- **Data / audit / detection** — tool-call logging, attribution (#200), trace/PII paths.

---

# Phase 2 — Tab generation (from `audit_state.json`)

Render each tab by filling its template in `templates/` from `audit_state.json`
ONLY (plus the template's headings). Write to `${ANALYSIS_DIR}/<date>/<file>.md`.

Two structural rules (enforce):
1. **Threat Model is the spine** — its Priority Review Areas link to the domain tabs.
2. **The Default/GitOps-vs-Read-Only-Advisor stance contrast lives ONLY in the
   Threat Model**; other tabs reference it, never restate it.

Authored tabs (template → output file):
`architectural_summary`, `threat_model`, `least_privilege_inventory`,
`secrets_token_brokering`, `agentic_prompt_injection`, `agentic_tools_mcp_trust`,
`agentic_skills_autonomy`, `admission_webhooks`, `runtime_hardening_network`,
`pipeline_cicd_supply_chain`, `data_audit_detection` (11 templates).

## Step 2a — Corrections processing

```
cd "${ANALYSIS_DIR}" && python3 -m tools.process_corrections "<date>" "${ANALYSIS_DIR}"
```
This ingests `corrections/inbox.md` into `corrections/ledger.jsonl` as `open`
entries, renders the Corrections tab (`<date>/corrections_feedback.md`), and
**rewrites the inbox to any unparsed lines** (exit 1 if so — no human comment is
lost). Then, for each active correction, verify it against current code and
advance its lifecycle (`open→confirmed|denied→absorbed→retired`); absorbed
corrections are applied to the relevant domain tab(s). **Never mark a correction
`denied` without deterministic tool-output proof** (the ledger enforces this).

## Step 2b — What's Changed

```
cd "${ANALYSIS_DIR}" && python3 -m tools.whats_changed "<date>" "${ANALYSIS_DIR}"
```
Curate the structured delta it emits (dir diff + findings added/removed/changed,
plus any Step-0 drift) into a human-readable `<date>/whats_changed.md`. First run
(no prior report): a short "baseline — no prior run" note.

## Step 2c — Findings rollup

```
cd "${ANALYSIS_DIR}" && python3 -m tools.findings_rollup "<date>" "${ANALYSIS_DIR}"
```
Renders the sprint-plannable **Findings** tab (`<date>/findings.md`) directly from
`audit_state.json` — a summary line, a Critical→Low action-item table (each row
grabbable by finding `id`), and a separated Informational section.

---

# Step 3 — Publish

```
${ANALYSIS_DIR}/generate.sh <date>
```
This re-runs the pre-flight + `audit_state.json` validation gates, then compiles
the 14 tabs into the Google Doc. Report the output URL.
