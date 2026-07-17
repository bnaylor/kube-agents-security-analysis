# Threat Model

## Component Overview

The kube-agents system consists of: a **Platform Agent** (single LLM-powered agent running in a GKE pod), a **Kubernetes Operator** (manages agent lifecycle and RBAC), an **Admission Webhook** (enforces singleton cardinality), a **LiteLLM Gateway** (proxies LLM API calls), a **GitHub Token Minter** (Minty, brokers short-lived GitHub tokens via KMS + OIDC), and **provisioning scripts** (set up GCP IAM, GKE clusters, K8s secrets).

The agent has: cluster-scoped Kubernetes read access (`view` ClusterRole), GCP project-level `gke-admin` IAM (by default), GitHub `contents:write` + `pull_requests:write` via Minty, and unrestricted network egress.

## Entry Points & Untrusted Inputs

### Primary Injection Vectors

| Vector | Path | Authenticated? | Frequency | Severity |
|---|---|---|---|---|
| **K8s pod logs/stdout** ([THREAT-001]) | `get_cc_pod_diagnostics()` MCP tool reads raw pod logs into LLM context | Cluster network | On-demand (agent triage) | **Critical** |
| **GitHub issues/comments** ([THREAT-002]) | `github-issue-resolver` cron polls every minute, feeds issue bodies into LLM context | Public (any GitHub user) | Every 60 seconds | **Critical** |
| **CRD spec fields** ([THREAT-004]) | `renderConfigYAML()` maps CRD fields → agent config.yaml; `buildSettingsConfigMap()` maps GitRepo → SETTINGS.md | K8s RBAC (CRD write) | On CR create/update | **High** |
| **Cloud Audit Logs** | `audit_log_searcher()` MCP tool returns log content to LLM; attacker-controlled resource names appear in audit entries | GCP IAM (read logs) | On-demand | **Medium** |
| **Chat messages** | Google Chat → Pub/Sub → agent context; Slack messages | Chat platform auth | Per message | **Medium** |
| **Multi-user memory** | `multiuser_memory` MCP tool persists/re-reads arbitrary content; injection persists across sessions | Agent pod filesystem | On tool use | **Medium** |

### Trust Propagation

[THREAT-003] (Critical): The `call_agent()` MCP tool creates a transitive trust chain:
1. Agent A is compromised via prompt injection (e.g., pod log)
2. Agent A uses `call_agent` to send an arbitrary query to Agent B
3. Delegation headers (user email, session ID) propagate the injected context downstream
4. Agent B trusts the incoming headers without cryptographic verification

This is compounded by the API_SERVER_KEY falling back to literal `"none"` — any pod in the cluster can forge the `Authorization: Bearer none` header and impersonate the inter-agent channel.

## Trust Boundaries & Auth Assumptions

| Boundary | Auth Mechanism | Weakness |
|---|---|---|
| Agent → GitHub (Minty) | OIDC token + KMS-signed JWT | Well-designed; OIDC audience fallback without `--audiences` is a minor gap |
| Agent → GKE API (MCP) | Workload Identity (GSA) | Default `gke-admin` is over-privileged; read-only option exists |
| Agent → K8s API | `view` ClusterRole + Explorer ClusterRole | Cluster-scoped read is broader than SOUL.md's stated "Read-Only visibility" |
| Agent → Agent (`call_agent`) | Shared static `API_SERVER_KEY` header | Falls back to `"none"`; no rotation, no per-agent scoping |
| Operator → K8s API | ClusterRole with `bind` on CRBs | Enables cluster-admin escalation if operator is compromised |
| Webhook → GCS (lock) | GCS client (ADC) | Lock is read-only in webhook; no release mechanism |
| Chat → Agent | Pub/Sub push | Authenticated via GCP, but chat content is untrusted input |

## Sensitive Data Paths

1. **API keys** (Gemini, OpenAI, Anthropic) → K8s Secret `platform-agent-secrets` → LiteLLM env vars → `/proc` accessible in container
2. **GitHub App private key** → CI secret → `/tmp/` on runner → KMS import (ephemeral disk exposure)
3. **User emails** → Google Chat → session_store SQLite (clear text, 7-day retention) → OTel spans (Cloud Trace) → Cloud Logging
4. **Tool call arguments/results** → `tool_call_audit` plugin → stdout (no redaction) → Cloud Logging
5. **Agent chat messages** → `chat_message_audit` hook → stdout (4000-char truncation, no content filtering) → Cloud Logging

## Privileged Actions Matrix (Default/GitOps vs Read-Only Advisor)

This tab is the **sole home** of the Default/GitOps-vs-Read-Only-Advisor stance contrast. Other tabs reference it; they do not restate it.

| Action | Default/GitOps Mode | Read-Only Advisor Mode |
|---|---|---|
| **K8s cluster mutations** | Via GitOps PR only (submit-suggestion); SOUL.md forbids direct kubectl apply | None (read-only `view` + Explorer roles) |
| **GKE cluster management** | `container.clusterAdmin` — full CRUD on GKE clusters via KCC or gcloud | `container.clusterViewer` — read-only |
| **GitHub writes** | `contents:write` + `pull_requests:write` via Minty token; agent creates branches, commits, PRs | Same token scopes — the "read-only" label is misleading: the agent retains a GitOps write channel |
| **GCP monitoring** | `monitoring.admin` — full access to monitoring config | `monitoring.viewer` — read-only |
| **IAM visibility** | `iam.securityReviewer` — read all IAM policies; `iam.serviceAccountUser` — impersonate any SA | `iam.securityReviewer` |
| **Cron autonomy** | All 10 cron jobs auto-approved (cron_mode: approve); github-issue-resolver runs every minute | Same — cron mode is not differentiated by agent stance |
| **Tool execution** | MCP tools: kubectl logs/describe, gcloud logging read, hermes notifications, call_agent | Same tool surface |
| **Network egress** | Unrestricted (no NetworkPolicy) | Unrestricted |

**Key insight**: The "Read-Only Advisor" is read-only against the *cluster control plane* (no kubectl apply/delete), but it is **not** zero-write. It holds a GitHub token with `contents:write` and `pull_requests:write`, autonomous cron execution, and notification capability. The distinction is about *which channel* mutations flow through, not about whether the agent can effect change.

## Out-of-Scope / False-Positive Criteria

- **Multi-agent delegation**: Only one agent type exists (platform). call_agent currently restricts target to `^(platform)$`. Multi-agent trust propagation is noted as architectural risk but is not an active finding.
- **Tenant isolation**: The system is designed for single-project, single-cluster operation. Multi-tenancy isolation (namespace-level RBAC, NetworkPolicies, ResourceQuotas) is a stated SOUL.md goal but not part of the current audit scope.
- **Model provider security**: The security of the underlying LLM (Gemini/OpenAI/Anthropic) is out of scope. This audit focuses on the agent harness, not the model.
- **Kubernetes itself**: Control plane security, etcd encryption, and node security are GKE-managed and out of scope.

## Priority Review Areas

| Priority | Domain Tab | Critical Findings | Primary Risk |
|---|---|---|---|
| **P0** | [Prompt Injection & Untrusted Input](#prompt-injection--untrusted-input) | 2 Critical | Pod logs + GitHub issues feed unsanitized into LLM context |
| **P0** | [Tools, MCP & Inter-Agent Trust](#tools-mcp--inter-agent-trust) | 1 Critical | API_SERVER_KEY "none" fallback + transitive call_agent trust |
| **P0** | [Runtime Hardening & Network](#runtime-hardening--network) | 1 Critical | No NetworkPolicy on the most privileged pod |
| **P1** | [Least-Privilege Inventory](#least-privilege-inventory) | 1 Critical | Operator has `bind` on ClusterRoles; default gke-admin is over-privileged |
| **P1** | [Admission Control (Webhooks)](#admission-control-webhooks) | 1 High | Webhook validates cardinality only, not security posture |
| **P1** | [Skills & Autonomy](#skills--autonomy) | 3 High | 10 auto-approved cron jobs, no skill provenance, unrestricted shell |
| **P2** | [GitOps & CI/CD Integrity](#gitops--cicd-integrity) | 1 High | No security scanning in CI pipeline |
| **P2** | [Secrets & Token Brokering](#secrets--token-brokering) | 2 High | Plaintext vars.sh, placeholder credentials in Secrets |
| **P2** | [Data, Audit & Detection](#data-audit--detection) | 2 High | No PII redaction in audit logs, unauthenticated session KV server |
