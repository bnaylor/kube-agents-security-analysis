---
onedoc_gdoc_url: REDACTED-GDOC-URL
onedoc_md_file_id: REDACTED
onedoc_tab_id: REDACTED
---
---
---
# Security Posture Synthesis: Default vs. YOLO Mode vs. Read-Only Advisor

This document synthesizes the security analysis of the `kube-agents` harness, comparing three operational stances:
1. **Default Stance**: The baseline configuration in the repository scripts.
2. **YOLO Stance**: The high-permission configuration analyzed in `YOLO_PERMISSIONS.md`.
3. **Read-Only Advisor Stance**: The hypothetical zero-write-privilege configuration for SRE debugging and PR recommendations.

> [!NOTE]
> **Single-Agent Architecture**: In the updated codebase, the multi-agent harness has consolidated into a **single unified Platform Agent** (`platform`). All analysis below reflects this single-agent architecture.

---

## 1. Comparative Stance & Privilege Matrix

| Dimension | Default Stance | YOLO Stance (`YOLO_PERMISSIONS.md`) | Read-Only Advisor Stance | Security Impact & Risk Analysis |
| :--- | :--- | :--- | :--- | :--- |
| **Platform Agent KSA (Host K8s)** | `view` ClusterRole + `kubeagents:explorer` ClusterRole | **`cluster-admin` RoleBinding** in `agent-system` | `view` ClusterRole + `kubeagents:explorer` ClusterRole | **YOLO Risk**: Full namespace `cluster-admin` allows pod/secret manipulation inside `agent-system`. |
| **Platform Agent GSA (GCP IAM)** | `container.admin`, `container.clusterAdmin`, `monitoring.admin`, `logging.admin`, `iam.securityReviewer` | **`container.admin`**, **`resourcemanager.projectIamAdmin`**, **`iam.serviceAccountAdmin`**, **`compute.admin`**, `viewer` | **`container.viewer`**, **`logging.viewer`**, **`monitoring.viewer`**, **`cloudtrace.user`**, **`iam.securityReviewer`** | **YOLO Critical**: `projectIamAdmin` allows complete GCP project takeover. **Read-Only Advantage**: Zero GCP write roles; immune to cloud mutation exploits. |
| **Mutation Channel** | Declarative GitOps PRs (Minty token broker) + direct API capability | Direct API calls + KCC with **`roles/owner`** project-wide | **Strictly Out-of-Band GitOps PRs** via Minty | **Read-Only Advantage**: 100% of mutations require human SRE review & GitOps reconciliation. |
| **Prompt Injection Exposure** | Moderate (Prompt instructions prevent direct API mutations, but IAM allows it) | **Critical** (Prompt injection can trigger immediate GCP IAM/resource destruction) | **Zero Write Footprint** (API calls for write operations are rejected at GCP IAM level) | **Read-Only Advantage**: Maximum safety against LLM output manipulation. |
| **Diagnostic & RCA Capability** | Full | Full | **Full** (Access to logs, metrics, traces, K8s state, and security drift audits) | Identical observability across all stances. |

---

## 2. Risk Evaluation & Privilege Escalation Paths

### 2.1. Critical Escalation in YOLO Stance
* **Path**: Prompt Injection ──> Platform Agent Pod ──> `roles/resourcemanager.projectIamAdmin` ──> **GCP Project Takeover**.
* **Mechanism**: In YOLO mode, the Platform Agent GSA is granted `roles/resourcemanager.projectIamAdmin` and `roles/iam.serviceAccountAdmin`. An attacker who tricks the agent via prompt injection can execute `gcloud projects add-iam-policy-binding`, granting themselves `roles/owner` on the GCP project.

### 2.2. Default Stance Vulnerability
* **Path**: Prompt Injection ──> Platform Agent Pod ──> `roles/container.admin` ──> Direct Cluster Mutation.
* **Mechanism**: While `SOUL.md` instructs the agent to use GitOps PRs, the default GSA holds `roles/container.admin`. A compromised agent pod can bypass prompt guidelines and directly delete GKE clusters or modify node pools via GCP APIs.

### 2.3. Neutralization in Read-Only Advisor Stance
* **Path**: Prompt Injection ──> Platform Agent Pod ──> `container.viewer` / `logging.viewer` ──> **Blocked by GCP IAM**.
* **Mechanism**: The agent GSA holds zero write roles in GCP IAM. Any attempted `gcloud` or REST API mutation call fails at the GCP IAM authorization layer. The agent can only produce recommendations and submit Pull Requests via Minty for human approval.

---

## 3. Master Hardening Checklist

To establish a secure production posture for `kube-agents`:

1. **Adopt Read-Only Advisor GCP IAM Profile**:
   * Revoke `roles/container.admin`, `roles/container.clusterAdmin`, `roles/monitoring.admin`, `roles/logging.admin`, `roles/iam.serviceAccountUser`, and `roles/resourcemanager.projectIamAdmin`.
   * Grant `roles/container.viewer`, `roles/logging.viewer`, `roles/monitoring.viewer`, `roles/cloudtrace.user`, and `roles/iam.securityReviewer`.
2. **Enforce Minty Token Brokering for GitOps**:
   * Require all PR recommendations to be signed using short-lived GitHub tokens retrieved from Minty.
   * Enforce PR review rules on the target GitOps repository so that human SREs must approve all agent suggestions before deployment.
3. **Harden Operator Webhook Validation**:
   * Implement validation checks in `platformagent_webhook.go` to reject system-reserved ServiceAccount names (`kubeagents-controller-manager`) and restrict Workload Identity GSA annotations.
