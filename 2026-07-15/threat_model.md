---
onedoc_gdoc_url: REDACTED-GDOC-URL
onedoc_md_file_id: REDACTED
onedoc_tab_id: REDACTED
---
---
---
# Security Threat Model: kube-agents

This threat model outlines the security boundaries, entry points, sensitive data paths, and priority review areas for the `kube-agents` harness, following the structure in the `determine-threat-model` skill and updated for the current single-agent architecture.

---

## 1. Component Overview (Repository Goal)

The `kube-agents` repository contains a single-agent Kubernetes operations harness centered around the **Platform Agent** (`platform`).
* **Platform Agent**: Acts as the unified gateway, frontend (Google Chat, Slack, REST API), fleet custodian, and SRE observer. It manages GKE infrastructure lifecycles, monitors telemetry, enforces multi-tenancy, and submits declarative infrastructure recommendations via GitOps PRs.
* **Kubernetes Operator (`k8s-operator`)**: Reconciles the `PlatformAgent` Custom Resource (`platformagents.kubeagents.x-k8s.io`) and manages its Deployment, ServiceAccounts, and RBAC bindings.

The deployment context assumes a GKE management cluster where the Operator and Platform Agent run, interacting with target clusters and GitOps repositories.

---

## 2. Entry Points and Untrusted Inputs

| Entry Point | Type | Trusted? | Validation / Mitigation |
| :--- | :--- | :--- | :--- |
| **User Chat (Google Chat / Slack)** | Messaging API | **No** | Authenticated via platform webhooks, but message payload (prompts) is untrusted. High risk of **Prompt Injection** attempting to trigger arbitrary commands or tool calls. |
| **Kubernetes API (PlatformAgent CRD)** | K8s API | **Yes** (Auth) | Authenticated via K8s RBAC. Validating webhooks enforce single-agent cardinality and GCS project-level locks. |
| **GitOps Repository (IaC)** | Git API | **Yes** (Auth) | Cloned by the agent to read infrastructure state (`SETTINGS.md`). Submissions require GitHub App tokens via Minty. |
| **LLM Completions API (LiteLLM Proxy)** | HTTP API | **No** | LiteLLM proxy is internal, but LLM output generation is untrusted. Agents parse LLM outputs to decide tool calls. |

---

## 3. Trust Boundaries and Auth Assumptions

* **User Prompt ──> Agent Runtime (Prompt Injection Boundary)**: External users interact with the agent via Google Chat/Slack. An attacker could inject malicious prompts attempting to execute shell commands (`kubectl`, `gcloud`), exfiltrate data, or alter cluster state.
* **Platform Agent ──> GCP Cloud APIs (Workload Identity Boundary)**:
  * *Default Stance*: The Platform Agent GSA holds `roles/container.admin`, `roles/container.clusterAdmin`, `roles/monitoring.admin`, and `roles/logging.admin`. A prompt injection compromise could lead to direct GCP API manipulation.
  * *Read-Only Advisor Stance*: The Platform Agent GSA holds `roles/container.viewer`, `roles/logging.viewer`, `roles/monitoring.viewer`, `roles/cloudtrace.user`, and `roles/iam.securityReviewer`. Prompt injection cannot execute GCP resource mutations.
* **Platform Agent ──> Minty Token Broker (OIDC Authentication Boundary)**: The agent uses its projected K8s ServiceAccount token (`X-OIDC-Token`) to authenticate to Minty. Minty verifies the OIDC claims against a CEL policy before issuing a 1-hour, repository-scoped GitHub token.
* **Platform Agent Pod ──> Host Kernel (Container Sandbox Boundary)**: The agent pod runs as non-root (`runAsUser: 10000`), drops all Linux capabilities (`Capabilities.Drop: ALL`), disables privilege escalation (`allowPrivilegeEscalation: false`), and uses `seccompProfile: RuntimeDefault`.

---

## 4. Sensitive Data Paths

| Data Type | Source | Destination | Protection |
| :--- | :--- | :--- | :--- |
| **LLM Provider API Keys** | K8s Secret | LiteLLM Pod | Stored in K8s Secrets (`platform-agent-secrets`), mounted only to LiteLLM. Agents do not handle raw LLM keys. |
| **GitHub App Private Key** | GCP KMS | KMS Internal Memory | Key material never leaves GCP KMS (`AsymmetricSign`). Minty delegates signing to KMS via RPC. |
| **GitHub Installation Tokens** | Minty Broker | Agent Pod | Short-lived (1-hour), scoped to target repository, written to `~/.git-credentials` with strict `0600` file mode. |
| **GKE KSA OIDC Tokens** | Projected Volume | Minty Broker | Short-lived, transmitted over internal HTTPS to authenticate token requests. |

---

## 5. Privileged Actions Matrix

| Action | Location | Default Stance Guard | Read-Only Advisor Stance Guard |
| :--- | :--- | :--- | :--- |
| **Mutate GKE Clusters / Node Pools** | GCP API / `gcloud` | Guarded only by LLM prompt rules (GSA has `container.admin`). High risk. | **Blocked at IAM level** (`container.viewer` rejects write calls). Zero risk. |
| **Delete / Alter Cloud Logs & Metrics**| GCP API | Guarded only by LLM prompt rules (GSA has `logging.admin`). | **Blocked at IAM level** (`logging.viewer` rejects write calls). Zero risk. |
| **Create / Update PlatformAgent CRs** | K8s API | K8s RBAC in `kubeagents-system` + Validating Webhook. | K8s RBAC restricted to read-only (`get`, `list`, `watch`). |
| **Submit GitOps Infrastructure PRs** | GitHub API | Guarded by Minty CEL policy + GitHub PR review gate. | Guarded by Minty CEL policy + GitHub PR review gate. |

---

## 6. Out-of-Scope / False Positive Criteria

The following scenarios are considered mitigated by standard GKE/Google Cloud production environments or represent intended advisory functionality, and are classified as **False Positives**:

* **Executing `kubectl get`, `gcloud container clusters list`, or log queries**: Intended functionality required for debugging, RCA, and fleet telemetry auditing.
* **Submitting Pull Requests to GitOps Repository**: Intended declarative workflow. Merging PRs is gated by human SRE review.
* **Standard Linux Container Escape (runc)**: Mitigated by running pods with non-root UID 10000, dropped capabilities, runtime default seccomp profiles, and optionally deploying on GKE gVisor node pools (`sandboxType: gvisor`).
* **Third-Party GCP API Vulnerabilities**: Flaws residing entirely within GCP backend services (e.g., Cloud Logging API) are out of scope for the harness.

---

## 7. Priority Review Areas & Recommendations

1. **Adopt Read-Only Advisor GCP IAM Profile**: Replace `roles/container.admin` and `roles/container.clusterAdmin` on the Platform Agent GSA with `roles/container.viewer`, `roles/logging.viewer`, `roles/monitoring.viewer`, and `roles/cloudtrace.user`.
2. **Harden Webhook Validation Gates**: Ensure the `PlatformAgent` validating webhook checks ServiceAccount names and prevents binding to system-critical identities.
3. **Enforce GitOps Human Review Gate**: Verify that all repository-scoped installation tokens minted by Minty restrict direct pushes to protected main branches and require Pull Request reviews.
