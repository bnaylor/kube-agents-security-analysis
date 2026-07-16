# kube-agents Security Audit Framework — Design

**Date:** 2026-07-16
**Author:** Brian Naylor (with Claude Code)
**Status:** Approved design, pending implementation plan

## 1. Context & Motivation

The `kube-agents-security-analysis` repo produces a repeatable, point-in-time
security report on the `kube-agents` codebase, published as a tabbed Google Doc
for human review.

The first-generation report (2026-07-15) and its
`generate-security-analysis-report` SKILL emerged from ad-hoc, top-of-mind
prompting of an internal Gemini harness. Two problems motivated this redesign:

1. **The SKILL drifts.** In ~3 weeks the codebase changed enough to invalidate
   ~5 concrete assumptions baked into the SKILL: it detected a multi-agent
   (`platform`/`operator`/`devteam`) model that no longer exists (operator &
   devteam agents removed in #256), inspected multi-agent webhooks, keyed off a
   `YOLO_PERMISSIONS.md` that no longer exists, hardcoded the `agent-system`
   namespace (renamed to `kubeagents-system`), and treated `agents/shared` as a
   directory (folded into `agents/platform` in #281).

2. **The coverage was infra-classic and missed the agentic attack surface.**
   The original 6 outputs covered RBAC, IAM, admission webhooks, and secrets —
   solid but generic. They barely touched what makes kube-agents *novel and
   risky*: an autonomous LLM agent with cluster-mutating capability.

This design rationalizes the outputs, expands coverage into a proper framework,
reworks the SKILL to resist drift, and adds a reviewer-feedback loop plus
run-over-run change summaries.

## 2. Goals / Non-Goals

**Goals**
- A stable, domain-organized report structure that is **diffable run over run**.
- First-class coverage of the **agentic/AI attack surface**.
- A SKILL that **re-grounds each run** instead of trusting stale paths.
- A **corrections ledger** so reviewer feedback is tracked to resolution.
- A **"What's Changed" TL;DR** so reviewers need not re-read the corpus.

**Non-Goals**
- Redesigning the `generate.sh` / onedoc → Google Doc publishing plumbing. We
  change *what* is produced, not *how* it is published. (Flagged as revisitable.)
- Fixing the findings themselves. This repo *reports*; fixes land in `kube-agents`.
- Automated pull of Google Doc comments (deferred; see §5.3).

## 3. Report Framework: 6 Domains, 13 Tabs

The Threat Model is the **spine**: its "priority review areas" link out to each
domain tab, and the Default/GitOps-vs-Read-Only-Advisor **stance contrast lives
only there** — every other tab references it rather than restating it.

| # | Tab | Domain | Filename |
|---|-----|--------|----------|
| 0 | What's Changed (TL;DR) | Front matter | `whats_changed.md` |
| 1 | Architectural & Security Summary | Foundation | `architectural_summary.md` |
| 2 | Threat Model | Foundation (spine) | `threat_model.md` |
| 3 | Least-Privilege Inventory | Identity & Access | `least_privilege_inventory.md` |
| 4 | Secrets & Token Brokering | Identity & Access | `secrets_token_brokering.md` |
| 5 | Prompt Injection & Untrusted Input | Agentic / AI | `agentic_prompt_injection.md` |
| 6 | Tools, MCP & Inter-Agent Trust | Agentic / AI | `agentic_tools_mcp_trust.md` |
| 7 | Skills & Autonomy | Agentic / AI | `agentic_skills_autonomy.md` |
| 8 | Admission Control (Webhooks) | Platform & Runtime | `admission_webhooks.md` |
| 9 | Runtime Hardening & Network | Platform & Runtime | `runtime_hardening_network.md` |
| 10 | GitOps & CI/CD Integrity | Pipeline & Supply Chain | `pipeline_cicd_supply_chain.md` |
| 11 | Data, Audit & Detection | Data & Detection | `data_audit_detection.md` |
| 12 | Corrections & Feedback Ledger | Living record | `corrections_feedback.md` |

Tab order is authoritative in `toc.md`; filenames are descriptive (no numeric
prefixes) to match existing convention.

### 3.1 Disposition of the original 6 outputs

| Original | Disposition |
|----------|-------------|
| `architectural_summary.md` | **Keep**, update to single-agent. Its "Privilege & Identity Matrix (Default vs Read-Only)" **moves to Threat Model** (dedup). |
| `threat_model.md` | **Keep + promote** to spine; sole home of the stance contrast. |
| `platform_agent_least_privilege_analysis.md` | **Keep, reframe** to a pure role/permission inventory → `least_privilege_inventory.md`. Stance framing removed (now in Threat Model). |
| `webhook_security_analysis.md` | **Keep, reassess** for the single `platformagent_webhook.go` → `admission_webhooks.md`. |
| `devteam_token_refresh_analysis.md` | **Reframe** → `secrets_token_brokering.md`. Drop the now-fixed namespace-bug framing (resolved by kube-agents #319); keep the enduring Minty/KMS/OIDC-CEL/0600 architecture. |
| `yolo_security_synthesis.md` | **Drop.** `YOLO_PERMISSIONS.md` no longer exists; the enduring stance contrast is preserved in the Threat Model. |

### 3.2 Tab section outlines

Each tab uses a fixed section outline so runs are diffable. Highlights of the
new/changed tabs:

- **Tab 2 — Threat Model (spine).** Component overview; entry points & untrusted
  inputs; trust boundaries & auth assumptions; sensitive data paths; **Privileged
  Actions Matrix (Default/GitOps vs Read-Only Advisor)** — the single home of the
  stance contrast; out-of-scope / false-positive criteria; **priority review
  areas** with links to the domain tabs below.
- **Tab 3 — Least-Privilege Inventory.** Platform Agent KSA ClusterRoles; Platform
  Agent GSA GCP IAM roles (from the IAM provisioning script); Config Connector /
  KCC roles. What is granted, whether it is minimal, where the excess is. No
  stance framing.
- **Tab 4 — Secrets & Token Brokering.** GitHub Token Broker (Minty) architecture;
  KMS-only signing (`AsymmetricSign`, no static private keys in pods); OIDC claim
  validation via CEL; short-lived scoped tokens; `0600` credential caching.
- **Tab 5 — Prompt Injection & Untrusted Input.** Enumerate untrusted input
  sources reaching the LLM context (GitHub issues/PRs, chat messages, logs, live
  cluster state); indirect-injection paths to tool calls; existing sanitization /
  guardrails; recommended layered defenses.
- **Tab 6 — Tools, MCP & Inter-Agent Trust.** MCP servers & tool inventory; tool
  scope/over-permission; confused-deputy risks; inter-agent auth (`call_agent`,
  `API_SERVER_KEY` — note the `"none"` default observed in
  `agent_common_server.py`).
- **Tab 7 — Skills & Autonomy.** Skill supply chain (`sync-upstream-skills.py`
  provenance/integrity); in-pod script execution risk; cron-driven autonomy and
  where human-in-the-loop gates exist / should exist.
- **Tab 8 — Admission Control (Webhooks).** The single `platformagent_webhook.go`:
  validation logic (cardinality, GCS project lock), gaps, hardening gates.
- **Tab 9 — Runtime Hardening & Network.** gVisor sandboxing (runtimeClass /
  nodepool); PodSecurity / SecurityContext (non-root, read-only rootfs, seccomp,
  capabilities); NetworkPolicy egress control / exfil paths.
- **Tab 10 — GitOps & CI/CD Integrity.** Mutation-channel safety (the
  `submit-suggestion` PR flow, branch protection, auto-merge posture, CI
  injection on agent PRs); GitHub Actions / prow workflow security (fold in
  existing `zizmor` posture); container image & dependency provenance.
- **Tab 11 — Data, Audit & Detection.** PII in chat/logs/traces & user
  attribution; audit-trail completeness & tamper-resistance (tool-call logging,
  attribution); detection & response for a misbehaving/compromised agent.

## 4. SKILL Rework

The reworked `generate-security-analysis-report` SKILL follows a **hybrid
intent + current-path-hints** style: every inspection step states *what to find*
first, then lists today's known paths as hints marked `as of 2026-07-16 —
verify`, and instructs the agent to re-ground each run.

- **Frontmatter/description.** Update from "6 files" to the 13 domain-organized
  outputs; single-agent reality; note the corrections ledger and TL;DR.
- **Step 1 — Path resolution.** Keep. Remove the fork/`upstream` split note
  (direct clone now); `KUBE_AGENTS_DIR` points at the clone.
- **Step 2 — Inspection (intent-first + dated hints).**
  - *Rewrites:* "single vs multi-agent" → "confirm the active agent set
    (expected: single `platform`)"; drop the `YOLO_PERMISSIONS.md` stance eval;
    drop the `agent-system` hardcode → "resolve the install namespace"; scope
    the webhook step to `platformagent_webhook.go`.
  - *New inspection intents:* untrusted input sources; MCP servers/tools &
    inter-agent auth; skill provenance & cron autonomy; runtime posture (gVisor
    runtimeClass, SecurityContext, NetworkPolicy); pipeline (Actions workflows,
    branch protection, auto-merge, image/dep pins); audit/data (tool-call
    logging, attribution, trace/PII paths).
- **Step 3 — File generation.** Emit the 13 files with fixed section outlines.
  Enforce the two structural rules: Threat Model is the spine; the stance
  contrast lives only in the Threat Model.
- **Step 3.5 — Corrections processing.** See §5.
- **Step 3.6 — What's Changed generation.** See §6.
- **Step 4 — Publish.** Keep the `generate.sh` trigger; update `toc.md` / `note.md`
  to the 13-tab list. Report the Google Doc URL.

## 5. Corrections & Feedback Ledger

### 5.1 Files (cross-run, top-level — not inside dated run folders)

- `corrections/inbox.md` — **intake**. Reviewers drop new comments here in a
  light structured format.
- `corrections/ledger.md` — **the persistent ledger** of all tracked corrections
  and their lifecycle.
- Per run, `corrections_feedback.md` (Tab 12) is a **rendered snapshot** of the
  ledger's active entries at run time.

### 5.2 Intake format (`inbox.md`)

Each new entry is a light block: `author`, `target` (tab + quoted report
statement), and `correction` (the claim). Example:

```
- author: Reviewer
  target: Secrets & Token Brokering — "Agents do not handle raw LLM keys"
  correction: The agent has access to the kubeagents-system namespace and can
    read ConfigMaps/Secrets that contain LLM API keys.
```

### 5.3 Ledger entry schema

`id`, `raised` (date), `author`, `target` (tab + quoted statement), `correction`,
`verification` (evidence as `file:line` / finding), `resolution` (report-update
ref and/or `kube-agents` PR link), `status`, and status-change dates.

### 5.4 Lifecycle state machine

```
Open ──▶ Confirmed ──▶ Absorbed ──▶ Retired
   └───▶ Denied (terminal)
```

- **Open** — captured from inbox, not yet assessed.
- **Confirmed** — verified true against current code (report was wrong/incomplete),
  with evidence.
- **Denied** — verified false; the report statement stands and the entry is kept
  as a *documented false-positive* (terminal).
- **Absorbed** — a confirmed correction has been folded into the relevant domain
  tab(s).
- **Retired** — the underlying issue is fixed in code or otherwise stable;
  archived out of the active view.

### 5.5 Per-run processing (SKILL Step 3.5)

1. Parse new `inbox.md` entries → create `Open` ledger entries; clear/archive the
   processed inbox blocks.
2. Re-verify every active (`Open`/`Confirmed`/`Absorbed`) entry against current
   code; record/update evidence.
3. Advance statuses: `Open`→`Confirmed`/`Denied`; apply `Confirmed` corrections
   into their tabs and mark `Absorbed`; mark `Retired` when fixed/stable.
4. Render the active ledger into Tab 12.

**Worked example (Reviewer).** Raised in inbox → `Open` → verify whether the
platform SA's RBAC permits reading Secrets/ConfigMaps in `kubeagents-system` →
`Confirmed` with `role.yaml:NN` evidence → **Absorb**: correct the "agents do not
handle raw LLM keys" statement in the Secrets & Least-Privilege tabs → `Retired`
once the report reflects it.

## 6. "What's Changed Since Last Run" (Tab 0)

At the end of a run, diff the current outputs against the previous dated run
(the latest date directory earlier than today) and write a **curated,
human-readable** summary (not a raw diff) to `whats_changed.md`, covering:

- New findings and resolved/changed findings per domain.
- **Corrections lifecycle deltas** (N confirmed, M absorbed, K denied, J retired).
- Structural changes (new/removed tabs).
- Notable posture shifts, e.g. *"kube-agents #319 fixed the token-refresh
  namespace default."*

This is the top tab so reviewers can skim what moved without re-reading the corpus.

## 7. Repo & Logistics

- The `kube-agents-security-analysis` directory is now a **git repo** (baseline
  commit `ff360e7`). Migration into the main `kube-agents` repo is an open option
  (see §8).
- **Gitignore** the derived onedoc cache: `**/.onedoc/snapshots/`.
- **Renames/removals** in the next dated run: `devteam_token_refresh_analysis.md`
  → `secrets_token_brokering.md`; add the agentic/runtime/pipeline/data tabs;
  drop `yolo_security_synthesis.md`; add `whats_changed.md` and
  `corrections_feedback.md`; add top-level `corrections/`.
- The 2026-07-15 outputs remain as the historical baseline; the new structure
  takes effect from the next run.

## 8. Open Items / Future

- **Migration decision:** whether this repo folds into `kube-agents` or stays
  external. Deferred; git history makes migration clean either way.
- **Automated comment ingestion:** pull reviewer comments directly from the
  Google Doc (onedoc snapshot cache or gdoc API) instead of manual `inbox.md`.
  The ledger schema is designed so this can slot in without rework.
- **Publishing plumbing:** `generate.sh` / onedoc mechanics left as-is; revisit
  if tab count or ordering strains it.
