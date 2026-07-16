---
onedoc_gdoc_url: REDACTED-GDOC-URL
onedoc_md_file_id: REDACTED
onedoc_tab_id: REDACTED
---
---
---
# Least Privilege Analysis: Platform Agent GCP Service Account (GSA) & K8s RBAC

This document analyzes the privilege models for the **Platform Agent** in the updated single-agent architecture. It evaluates the current default stance and details a **hypothetical Read-Only Advisor scenario** where the agent holds strictly read-only access across Kubernetes and GCP resources.

---

## 1. Current Privilege Baseline (Default Stance)

In the default deployment script ([provision_03_gcp_iam.sh](k8s-operator/scripts/provision_03_gcp_iam.sh#L154)), the Platform Agent's GCP Service Account (`platform-agent-sa`) is granted the following project-wide roles:

* `roles/container.admin` (Kubernetes Engine Admin)
* `roles/container.clusterAdmin` (Kubernetes Engine Cluster Admin)
* `roles/monitoring.admin` (Monitoring Admin)
* `roles/logging.admin` (Logging Admin)
* `roles/iam.serviceAccountUser` (Service Account User)
* `roles/iam.securityReviewer` (Security Reviewer)

On the management Kubernetes cluster, the agent's KSA (`platform-agent`) is bound to:
* `view` ClusterRole (standard read-only access across namespaces)
* `kubeagents:explorer` ClusterRole (read access to `nodes`, `pods`, `namespaces`, and `customresourcedefinitions`)

### Security Evaluation of Default Stance
* **Discrepancy**: The agent's core instructions ([SOUL.md: L11](agents/platform/SOUL.md#L11)) mandate a **Declarative First / GitOps Workflow**, strictly forbidding manual cluster API mutations. However, its GCP GSA holds full `container.admin` privileges.
* **Prompt Injection Threat**: Because the agent is user-facing (exposed to Google Chat, Slack, or webhooks), a successful prompt injection attack could allow an adversary to invoke `gcloud` or `kubectl` tools with full GKE administrative rights, bypassing declarative PR review gates.

---

## 2. Hypothetical Read-Only Advisor Scenario

In this scenario, the Platform Agent is configured as a **purely advisory SRE observer**. It holds **zero write privileges** across Kubernetes and Google Cloud APIs. Its primary functions are real-time telemetry inspection, root-cause analysis (RCA), security drift auditing, and submitting declarative GitOps recommendations (Pull Requests).

### 2.1. Read-Only GCP IAM Configuration
The GSA is stripped of all administrative and mutation roles, retaining strictly read-only visibility:

| Role | Status | Purpose |
| :--- | :--- | :--- |
| `roles/container.viewer` | **Granted** | Inspect GKE cluster metadata, node pool states, and pod status via GCP APIs. |
| `roles/logging.viewer` | **Granted** | Query Cloud Logging for container logs, error traces, and system events. |
| `roles/monitoring.viewer` | **Granted** | Query Cloud Monitoring / Prometheus metrics for CPU, memory, and latency SLOs. |
| `roles/cloudtrace.user` | **Granted** | Read distributed OpenTelemetry traces for microservice performance debugging. |
| `roles/iam.securityReviewer` | **Granted** | Audit GCP IAM roles and Workload Identity bindings for security compliance. |
| `roles/container.admin` | **Revoked** | Prevents API-level cluster modifications or node pool deletions. |
| `roles/container.clusterAdmin` | **Revoked** | Prevents direct cluster administration. |
| `roles/monitoring.admin` | **Revoked** | Prevents modification of alerting policies or notification channels. |
| `roles/logging.admin` | **Revoked** | Prevents modification or deletion of log sinks and audit logs. |
| `roles/iam.serviceAccountUser` | **Revoked** | Prevents attaching or assuming arbitrary GCP service accounts. |

### 2.2. Read-Only Kubernetes RBAC Configuration
* **ServiceAccount**: `platform-agent` in `kubeagents-system`.
* **Bindings**:
  * `view` ClusterRoleBinding (read-only access to standard Kubernetes resources).
  * `kubeagents:explorer` ClusterRoleBinding (read-only access to `nodes`, `pods`, `namespaces`, `customresourcedefinitions`).
* **Enforcement**: Zero `create`, `update`, `patch`, or `delete` verbs granted to the agent ServiceAccount.

### 2.3. Out-of-Band Mutation Flow (GitOps Pull Requests)
When the Read-Only Advisor Agent identifies a problem (e.g. crashing pod due to resource throttling, missing NetworkPolicy, or out-of-date image):

```
[Agent Pod (Read-Only GSA)]
     │
     ├── 1. Read telemetry (Logs, Metrics, K8s State)
     ├── 2. Perform RCA & Generate Recommended Fix (YAML)
     │
     ▼ 3. Request short-lived PR token via OIDC
[Minty Token Broker] ──(Signs JWT via KMS)──> [GitHub API]
     │
     ▼ 4. Create Feature Branch & Submit Pull Request
[GitOps Infrastructure Repository]
     │
     ▼ 5. Human SRE Reviews & Merges PR
[GitOps Controller (ArgoCD/Flux/KCC)] ──(Applies Fix)──> [Target GKE Cluster]
```

1. **Token Brokering**: The agent authenticates to **Minty** using its projected GSA OIDC token.
2. **PR Creation**: Minty issues a 1-hour GitHub installation token scoped exclusively to feature branches (`pull_requests: write`, `contents: write`).
3. **Human Gate**: The agent invokes `submit-suggestion` to open a Pull Request.
4. **Reconciliation**: A human SRE reviews the PR. Once merged, an independent GitOps controller (ArgoCD, Flux, or Config Connector) applies the change to the cluster.

---

## 3. Comparative Stance Analysis

| Dimension | Default Stance | Declarative GitOps Stance | Read-Only Advisor Scenario |
| :--- | :--- | :--- | :--- |
| **GCP GKE Control** | `container.admin` (Full mutation) | `container.viewer` | `container.viewer` (Strictly read-only) |
| **GCP Telemetry Control** | `logging.admin`, `monitoring.admin` | `logging.viewer`, `monitoring.viewer` | `logging.viewer`, `monitoring.viewer`, `cloudtrace.user` |
| **K8s RBAC Control** | `view` + `explorer` ClusterRoles | `view` + `explorer` ClusterRoles | `view` + `explorer` ClusterRoles |
| **Direct Mutation Risk** | **High**: Attacker can alter cloud/cluster state via tools | **Low**: Policy mandates PRs, but IAM allows direct calls | **Zero**: GCP and K8s APIs reject all write calls |
| **Prompt Injection Exposure** | Attacker can manipulate infrastructure directly | Attacker could attempt API calls (gcloud blocks) | Attacker can only trigger queries or PR suggestions |
| **Debugging & RCA Capability** | Full | Full | **Full** (All diagnostic logs, metrics, traces accessible) |
| **SRE Value Proposition** | Autonomous execution & self-healing | Human-reviewed PR automation | **Risk-Free SRE Copilot & Automated RCA** |

---

## 4. Implementation Guide for Read-Only Stance

To switch the harness to the **Read-Only Advisor Scenario**, modify [provision_03_gcp_iam.sh](k8s-operator/scripts/provision_03_gcp_iam.sh#L154):

```bash
# Step 3: Configure Platform Agent IAM (Read-Only Advisor Profile)
verify_platform_agent() {
  verify_agent_iam "${PLATFORM_AGENT_KSA_NAME}" "${PLATFORM_AGENT_GSA_NAME}" \
      "roles/container.viewer" \
      "roles/monitoring.viewer" \
      "roles/logging.viewer" \
      "roles/cloudtrace.user" \
      "roles/iam.securityReviewer"
}
execute_platform_agent() {
  execute_agent_iam "Platform Agent (Read-Only Advisor)" "${PLATFORM_AGENT_KSA_NAME}" "${PLATFORM_AGENT_GSA_NAME}" \
      "roles/container.viewer" \
      "roles/monitoring.viewer" \
      "roles/logging.viewer" \
      "roles/cloudtrace.user" \
      "roles/iam.securityReviewer"
}
```

This configuration provides maximum security against prompt injection and privilege escalation while maintaining 100% of the agent's diagnostic, RCA, and PR recommendation capabilities.
