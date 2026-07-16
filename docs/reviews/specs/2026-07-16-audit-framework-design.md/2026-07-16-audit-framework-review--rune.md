# Review: kube-agents Security Audit Framework Design

**Target:** `/shared/agents/scromp/inbox/2026-07-16-audit-framework-design.md`
**Author:** Brian Naylor (with Claude Code)
**Status:** Approved design, pending implementation plan

---

This is a well-reasoned design that clearly learned from v1's failures (skill drift, stale paths, the `agent-system` hardcode, the `YOLO_PERMISSIONS.md` assumption). The 6-domain, 13-tab structure is clean and the corrections ledger lifecycle is a significant improvement. The observations below are structural rather than line-item bugs — things to watch in implementation.

---

## 1. The drift-resistance mechanism is good in theory, fragile in execution

The "intent-first + dated hints" approach (`as of 2026-07-16 — verify`) is the right pattern. But it's purely instructional. There is no mechanical enforcement that the LLM actually re-grounds — the skill *says* "re-ground each run" but nothing makes it.

If the LLM shortcuts and reads the known-path hints as ground truth instead of verifying them, drift re-emerges silently. The whole point of this redesign was that the v1 skill baked stale assumptions — the v2 skill still relies on the LLM to notice they're stale and act on it.

**Recommendation:** Add a lightweight **pre-flight verification step** before the inspection loop begins. Something like:

```
Pre-flight:
  - `test -f agents/platform/config.yaml` — confirm multi-agent model removed
  - `kubectl get ns kubeagents-system` — confirm install namespace
  - `stat agents/platform/scripts/platform_mcp_server.py` — confirm paths alive
  - abort with diff report if any check fails
```

This turns drift from a silent risk into a hard failure that shows up in the "What's Changed" tab before any inspection code runs.

---

## 2. The corrections ledger lifecycle depends on a human remembering to copy comments

The inbox → ledger flow is manual. A reviewer writes a comment on the Google Doc. Someone has to notice it, copy it into `corrections/inbox.md`, and the next run picks it up. If nobody remembers, the ledger silently stagnates.

The design defers automated ingestion (right call — don't scope-creep this iteration), but a lightweight intermediate step could help bridge the gap: the last-generation date and a "ready for review" signal published somewhere reviewers actually look (Slack notification, GitHub issue, PR comment on the run artifacts).

**Recommendation:** Pick a notification channel for "new report ready — corrections due" that doesn't require someone to remember to check. Even a low-effort `gh issue create` or webhook ping in `generate.sh` would help.

---

## 3. `API_SERVER_KEY: "none"` needs a cross-reference to a fix, not just a flag

Tab 6 correctly flags the `"none"` default for `API_SERVER_KEY` in the inter-agent auth section. But the design stops at "here's a finding." For something this severe (no auth between agents = any agent can impersonate any other), this finding will cycle every run with the same answer until someone does something about it.

**Recommendation:** The Threat Model spine should link this to a concrete action — either a `kube-agents` issue number or a PR that adds proper secret-based key rotation. Without that link, the finding has no home and no owner, and the report just keeps saying "still none."

---

## 4. The SRE read-only agent's GitOps PR flow creates a write path that needs explicit modeling in Tab 10

PR #315 just landed an SRE read-only agent that opens remediation PRs on the GitOps repo. That's the designed behavior — but it means the SRE agent, which is "read-only" against the cluster, has write access to the GitOps repo via its GitHub token.

The CI/CD integrity tab (Tab 10) should model this path explicitly:

- **Who opens PRs?** The SRE agent's GitHub identity (same token as platform agent? separate?).
- **Who merges them?** Are branch protection rules different for SRE-agent-authored PRs?
- **What happens when CI runs on an SRE-agent-authored commit?** CI triggers have the same blast radius whether the commit was authored by a human or an LLM. If the CI pipeline deploys on merge, the SRE agent's PR is one review away from cluster mutation.

This isn't a bug — it's the intended design. But the threat model should trace this as a trust path because it's a write channel through a (deliberate, gated) proxy.

---

## 5. Tab 11 — detection is the hardest tab in the framework

The data, audit, and detection tab is crucial but its scope isn't well-bounded in this design. Tool-call logging gives you forensics *after* something happens, but the design doesn't distinguish between:

- **What's feasible now** (structured audit logs, tool-call attribution, egress monitoring via NetworkPolicy)
- **What's aspirational** (behavioral anomaly detection, real-time compromised-agent response)

If the agent has cluster-mutating capability, "we'll figure out detection later" is a gap that matters. A compromised agent with `kubectl apply` access and NetworkPolicy write privileges can exfiltrate before anyone looks at the logs.

**Recommendation:** Bucket Tab 11 into "implemented / feasible / aspirational" sections so the design surfaces what actually protects the cluster vs. what's on the roadmap. Flag the response-time expectation: if a compromise happens at 3am, what detects it and who gets paged?

---

## Summary

| # | Area | Severity | Concern |
|---|------|----------|---------|
| 1 | Pre-flight verification | Medium | Drift-resistance is instructional, not mechanical |
| 2 | Corrections lifecycle | Medium | Manual inbox copy step is fragile |
| 3 | API_SERVER_KEY | High | No owner/PR link for the most severe finding |
| 4 | GitOps write path | Medium | SRE agent's PR flow is a trust boundary that needs modeling |
| 5 | Detection scope | Medium | Vague on what's feasible vs. aspirational |

The framework structure is sound. The re-grounding strategy is the right idea — the implementation just needs mechanical enforcement to make it stick.
