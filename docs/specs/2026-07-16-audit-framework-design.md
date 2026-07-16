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
- Automated pull of Google Doc comments. **Not deferred — infeasible:** the
  Google Docs API does not export comments (confirmed by the author), so the
  structured `corrections/inbox.md` is the *permanent* intake path, not a
  stopgap. (Rejects peer-review suggestion Iris #4.)
- A programmatic Markdown structural linter (Iris #1) — deferred as YAGNI; see §8.
- A local HTML report generator — wanted, but explicitly out of scope for this
  iteration; see §8.

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
  areas** with links to the domain tabs below. Two cross-cutting rules
  (peer review):
  - *Read-only ≠ zero-write (Clomp #3 / Iris #5 / Rune #4):* the Read-Only
    Advisor stance is read-only **against the cluster/GCP**, but still holds a
    **GitOps write channel** via its GitHub token (it opens remediation PRs).
    The stance matrix must state this explicitly so "read-only is safe" is not
    overclaimed; the mechanics are audited in Tab 10.
  - *Findings carry an owner/tracking link (Rune #3):* each material finding
    records a `kube-agents` issue/PR link (or `UNTRACKED`) so recurring findings
    like `API_SERVER_KEY: "none"` have a home and don't re-report forever with no
    action. Same `file:line`-evidence discipline as the corrections ledger.
- **Tab 3 — Least-Privilege Inventory.** Platform Agent KSA ClusterRoles; Platform
  Agent GSA GCP IAM roles (from the IAM provisioning script); Config Connector /
  KCC roles. What is granted, whether it is minimal, where the excess is. No
  stance framing.
- **Tab 4 — Secrets & Token Brokering.** GitHub Token Broker (Minty) architecture;
  KMS-only signing (`AsymmetricSign`, no static private keys in pods); OIDC claim
  validation via CEL; short-lived scoped tokens; `0600` credential caching.
- **Tab 5 — Prompt Injection & Untrusted Input.** Enumerate untrusted input
  sources reaching the LLM context. In a vanilla corporate environment the
  **Kubernetes API is the primary indirect-injection vector** (Clomp #4):
  explicitly treat **pod logs / container `stdout`, labels, annotations, CRD
  specs, and events** as untrusted — a tenant who knows the agent scans pod logs
  during triage can embed injections in their app's output to hijack the agent's
  context. Plus GitHub issues/PRs and chat messages. Cover indirect-injection
  paths to tool calls; existing sanitization / guardrails; recommended layered
  defenses (author's prior 3-tier prompt-sanitizing work applies here).
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
  **Read-only SRE agent write-channel audit** (Clomp #3 / Iris #5 / Rune #4;
  grounded in the *open* PR #315 `feat/add-sre-readonly-mode`, so this audits
  the design before it lands):
  1. *Identity separation* — the SRE agent must use a **distinct** GitHub
     App/PAT identity, **not** the master Platform Agent's (PR #315 reportedly
     copy-pasted `submit-suggestion` and inherited it — verify).
  2. *No self-approval / no bypass* — branch protection must bar the SRE agent's
     identity from approving its own PRs or bypassing required reviews/merge
     gates.
  3. *CI environment gates* — CI must require a human approve-to-run gate before
     building/deploying/running integration tests on agent-authored commits, so
     a compromised agent can't inject into CI. Merge-triggered deploy = one
     review from cluster mutation.
- **Tab 11 — Data, Audit & Detection.** PII in chat/logs/traces & user
  attribution; audit-trail completeness & tamper-resistance (tool-call logging,
  attribution); detection & response for a misbehaving/compromised agent.
  Bucket the tab into **Implemented / Feasible-now / Aspirational** (Rune #5) so
  the report distinguishes what actually protects the cluster today from
  roadmap. Force the response-time question explicitly: *if a compromise happens
  at 3am, what detects it and who gets paged?* — an agent with cluster-mutating
  capability can exfiltrate faster than a human reads logs, so post-hoc
  forensics alone is an unacceptable answer.

## 4. SKILL Rework

The reworked `generate-security-analysis-report` SKILL follows a **hybrid
intent + current-path-hints** style: every inspection step states *what to find*
first, then lists today's known paths as hints marked `as of 2026-07-16 —
verify`. Two mechanisms keep it honest rather than relying on the LLM to
"remember" to re-ground (peer review: Rune #1, Iris #2):

1. A **mechanical pre-flight** that fails hard on drift before any analysis.
2. A **two-phase execution** (inspect → `audit_state.json` → render) so the 13
   tabs are generated from a single ground-truth artifact, not a saturated
   conversation.

- **Frontmatter/description.** Update from "6 files" to the 13 domain-organized
  outputs; single-agent reality; note the corrections ledger and TL;DR.

- **Step 0 — Pre-flight verification (mechanical, hard-fail).** Before any
  inspection, run a small script that asserts the dated path-hints still
  resolve. If any check fails, **abort** and record the mismatch as the first
  entry in the run's "What's Changed" tab (so drift surfaces loudly instead of
  silently). Seed checks (extend as the codebase moves):
  ```
  test -f agents/platform/config.yaml          # single-agent model intact
  test -d agents/platform && ! test -d agents/operator && ! test -d agents/devteam
  test -f agents/platform/scripts/platform_mcp_server.py
  kubectl get ns kubeagents-system             # install namespace (if cluster reachable)
  ```

- **Phase 1 — Inspection & state export (→ `audit_state.json`).** Perform code
  discovery, RBAC/IAM scanning, MCP/tool enumeration, runtime/pipeline posture
  checks, and ledger verification, writing all findings to a single structured
  ground-truth artifact `audit_state.json`. Inspection intents:
  - *Rewrites of the v1 steps:* "single vs multi-agent" → "confirm the active
    agent set (expected: single `platform`)"; drop the `YOLO_PERMISSIONS.md`
    stance eval; drop the `agent-system` hardcode → "resolve the install
    namespace"; scope the webhook step to `platformagent_webhook.go`.
  - *New inspection intents:* untrusted input sources (incl. **K8s pod
    logs/stdout, labels, annotations, CRD specs, events** — see Tab 5); MCP
    servers/tools & inter-agent auth (incl. the `API_SERVER_KEY: "none"`
    fallback); skill provenance & cron autonomy; runtime posture (gVisor
    runtimeClass, SecurityContext, NetworkPolicy); pipeline (Actions workflows,
    branch protection, auto-merge, image/dep pins, **the read-only SRE agent
    GitOps write-channel — kube-agents PR #315**); audit/data (tool-call
    logging, attribution, trace/PII paths).

- **Phase 2 — Tab generation (from `audit_state.json`).** Render each of the 13
  tabs, reading *only* `audit_state.json` plus that tab's section template, in a
  fresh/low-context pass. This guarantees cross-tab consistency (no tab
  contradicting another) and keeps context small. Enforce the two structural
  rules: Threat Model is the spine; the stance contrast lives only in the Threat
  Model.
  - **Step 2a — Corrections processing.** See §5.
  - **Step 2b — What's Changed generation.** See §6.

- **Step 3 — Publish.** Keep the `generate.sh` trigger; update `toc.md` /
  `note.md` to the 13-tab list. Report the Google Doc URL. *(A programmatic
  Markdown structural linter — Iris #1 — is deferred; see §8.)*

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
  as a *documented false-positive* (terminal). **Guardrail against the LLM
  gaslighting reviewers (Clomp #2):** an entry may move to `Denied` **only** with
  deterministic tool-output proof that the claim is false (e.g. a grep/`kubectl`
  result directly contradicting it). Absent such proof, the human's claim is
  treated as ground truth and the entry stays `Open`/`Confirmed` pending a human
  — the LLM must never `Deny` a human correction on the basis of its own
  reasoning alone.
- **Absorbed** — a confirmed correction has been folded into the relevant domain
  tab(s).
- **Retired** — the underlying issue is fixed in code or otherwise stable;
  archived out of the active view.

### 5.5 Per-run processing (SKILL Phase 2, Step 2a)

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

At the end of a run, produce the change summary in two steps (Iris #3): first run
a **deterministic diff** (`git diff --no-index` of the previous vs. current dated
dirs, and/or a diff of the previous vs. current `audit_state.json`) to get
precise, complete deltas including single-line permission changes; then feed that
diff to the LLM to write a **curated, human-readable** summary (not a raw diff) to
`whats_changed.md`. This avoids making the LLM read ~26 markdown files and
guarantees subtle changes aren't missed. The summary covers:

- **Pre-flight drift** (Step 0): any path-hint that failed, surfaced first.
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
- **New per-run artifact:** `<YYYY-MM-DD>/audit_state.json` — the Phase-1
  ground-truth export that Phase-2 tab generation and the What's Changed diff
  both read from (§4, §6). Committed with the run (it *is* the diffable state).
- **New helper scripts** (`tools/`): the Step-0 pre-flight checker and a
  deterministic `diff_reports.sh` (`git diff --no-index`) for What's Changed.
  (`validate_structure.py` is deferred — §8.)
- **Renames/removals** in the next dated run: `devteam_token_refresh_analysis.md`
  → `secrets_token_brokering.md`; add the agentic/runtime/pipeline/data tabs;
  drop `yolo_security_synthesis.md`; add `whats_changed.md` and
  `corrections_feedback.md`; add top-level `corrections/`.
- The 2026-07-15 outputs remain as the historical baseline; the new structure
  takes effect from the next run.

## 8. Open Items / Future

- **Migration decision:** whether this repo folds into `kube-agents` or stays
  external. Deferred; git history makes migration clean either way.
- **Lightweight HTML report generator (author request, deferred):** a local
  HTML generator that runs in-repo, as an alternative/companion to the Google
  Doc. Two things fold into this when built: (a) a **"report ready / corrections
  due" signal** for reviewers (Rune #2) — parked here rather than bolted onto
  `generate.sh`; (b) reduced dependence on the onedoc/gdoc pipeline.
- **Markdown structural linter (Iris #1), deferred:** a `tools/validate_structure.py`
  that hard-fails `generate.sh` on missing files / bad frontmatter / missing
  required headings. Not needed until truncation/omission is actually observed;
  the Step-0 pre-flight already covers *path* drift.
- **Automated comment ingestion — closed, not open:** ruled out (Docs API has no
  comment export). `corrections/inbox.md` is permanent. Any future automation
  would come via the HTML-generator path, not the Docs API.
- **Publishing plumbing:** `generate.sh` / onedoc mechanics left as-is; revisit
  if tab count or ordering strains it (or when the HTML generator lands).

## 9. Peer Review Disposition

Three peer reviews (`docs/reviews/specs/2026-07-16-audit-framework-design.md/`)
from Clomp, Iris, and Rune. Evaluated as input, not instructions; verified
against the codebase before adoption.

| Review point | Disposition | Where |
|---|---|---|
| Clomp #2 — ledger anti-gaslighting guardrail | **Accepted** | §5.4 |
| Clomp #3 / Iris #5 / Rune #4 — SRE read-only GitOps write-channel | **Accepted** (verified: PR #315 is *open*) | Tab 10, Tab 2 |
| Clomp #4 — K8s API (pod logs/labels/annotations/CRD) as untrusted input | **Accepted** | Tab 5 |
| Rune #1 — mechanical pre-flight vs. instructional-only drift resistance | **Accepted** (verified paths) | §4 Step 0 |
| Rune #3 — findings need owner/tracking link | **Accepted** (verified `API_SERVER_KEY:"none"`) | Tab 2 |
| Rune #5 — bucket detection implemented/feasible/aspirational + page question | **Accepted** | Tab 11 |
| Iris #2 — two-phase inspect→`audit_state.json`→render | **Accepted** (ignored the unsubstantiated "70%" claim) | §4 |
| Iris #3 — deterministic pre-diff feeds What's Changed | **Accepted** | §6 |
| Iris #1 — Markdown structural linter as hard gate | **Deferred** (YAGNI until truncation observed) | §8 |
| Rune #2 — "report ready / corrections due" notification | **Deferred** into the HTML-generator phase | §8 |
| Iris #4 — automated gdoc comment scraping | **Rejected** — Docs API has no comment export | §2, §8 |
