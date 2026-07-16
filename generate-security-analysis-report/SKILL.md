---
name: generate-security-analysis-report
description: Audits the kube-agents repository security posture, generates 6 date-stamped markdown analysis files directly in ~/src/kube-agents-security-analysis/<YYYY-MM-DD>/, and triggers tabbed Google Doc generation.
---

# Task
Perform a comprehensive security audit of the `kube-agents` repository. Analyze the current codebase architecture, RBAC bindings, GCP IAM permissions, admission webhooks, and token brokering setup. Generate 6 date-stamped Markdown analysis files directly in `${SRC_DIR:-$HOME/src}/kube-agents-security-analysis/<YYYY-MM-DD>/` and invoke `generate.sh` to produce a tabbed Google Doc.

---

# Execution Steps

## Step 1: Target Directory & Path Resolution
1. Resolve environment paths:
   - `SRC_DIR="${SRC_DIR:-$HOME/src}"`
   - `KUBE_AGENTS_DIR="${KUBE_AGENTS_DIR:-$SRC_DIR/kube-agents}"`
   - `ANALYSIS_DIR="${ANALYSIS_DIR:-$SRC_DIR/kube-agents-security-analysis}"`
2. Obtain the target UTC date in `YYYY-MM-DD` format (e.g. `2026-07-15`).
3. Set the target output directory:
   `${ANALYSIS_DIR}/<YYYY-MM-DD>/`
4. Ensure the target directory exists (`mkdir -p`).

## Step 2: Codebase Architecture & Security Inspection
Audit the target repository (`${KUBE_AGENTS_DIR}`) to capture current operational realities:
1. **Agent Architecture**: Check `agents/` and `README.md` to identify whether the repository uses a single-agent (`platform`) or multi-agent (`platform`, `devteam`, `operator`) model.
2. **Custom Resources**: Inspect `k8s-operator/api/v1alpha1/` to identify active Custom Resource Definitions (e.g., `PlatformAgent`).
3. **Controller Logic & RBAC**: Inspect `k8s-operator/internal/controller/` to determine controller privileges and generated Kubernetes RBAC roles (`ClusterRole`, `ClusterRoleBinding`).
4. **Admission Webhooks**: Inspect `k8s-operator/internal/webhook/` to evaluate active mutating/validating webhooks (cardinality checks, GCS locks, validation gates).
5. **GCP IAM Permissions**: Inspect `k8s-operator/scripts/provision_03_gcp_iam.sh` to determine the GCP IAM roles granted to agent Google Service Accounts (GSAs).
6. **Token Brokering**: Inspect `integrations/github/` and `agents/platform/scripts/github_token_refresh.py` to evaluate GitHub Token Broker (Minty) integration, OIDC claims, and KMS key usage.
7. **YOLO Stance Evaluation**: Check for external/branch permission documentation (such as `YOLO_PERMISSIONS.md`) or active branch configurations to compare against default templates.

## Step 3: Markdown Files Generation
Directly write the following 6 Markdown files inside `${ANALYSIS_DIR}/<YYYY-MM-DD>/`:

### 1. `architectural_summary.md`
- System Architecture & Agent Model (single-agent vs multi-agent).
- Component Directory & Role Analysis.
- Privilege & Identity Matrix (Default Stance vs Read-Only Advisor Stance).
- Key Security Boundaries.
- Mermaid System Diagram (MUST use valid quoted subgraph syntax, e.g., `subgraph "Management Cluster (GKE)"`).

### 2. `threat_model.md`
- Follow standard `determine-threat-model` structure:
  - Component Overview
  - Entry Points & Untrusted Inputs
  - Trust Boundaries & Auth Assumptions
  - Sensitive Data Paths
  - Privileged Actions Matrix (Default vs Read-Only Advisor)
  - Out-of-Scope / False Positive Criteria
  - Priority Review Areas

### 3. `webhook_security_analysis.md`
- Webhook Audit of active handlers in `k8s-operator/internal/webhook/`.
- Current Validation Logic (Cardinality, GCS Project Lock).
- Identified Security Gaps & Proposed Hardening Gates (ServiceAccount restrictions, Workload Identity annotation checks, image/env sanitization).
- Draft Go Validation Implementation Snippets.

### 4. `platform_agent_least_privilege_analysis.md`
- Current Privilege Baseline (`roles/container.admin`, `roles/container.clusterAdmin`, `roles/monitoring.admin`, `roles/logging.admin`, `roles/iam.serviceAccountUser`, `roles/iam.securityReviewer`).
- Profile A (Declarative GitOps Stance).
- **Profile B (Hypothetical Read-Only Advisor Scenario)**:
  - Complete read-only visibility (`container.viewer`, `logging.viewer`, `monitoring.viewer`, `cloudtrace.user`, `iam.securityReviewer`).
  - Zero write access to K8s cluster or GCP APIs.
  - Out-of-band mutation flow via Minty PR recommendations.
- Comparative Stance Analysis & Implementation Guide for `provision_03_gcp_iam.sh`.

### 5. `devteam_token_refresh_analysis.md`
- Security analysis of GitHub Token Broker (Minty) integration.
- OIDC claim validation (`X-OIDC-Token`).
- GCP KMS RSA signing (`AsymmetricSign`).
- Credential caching with `0600` file modes in `~/.git-credentials`.
- Single-agent platform token refresher script workflow and CEL policy scope requirements.

### 6. `yolo_security_synthesis.md`
- Comparative Stance Matrix: Default Stance vs YOLO Stance (`YOLO_PERMISSIONS.md`) vs Read-Only Advisor Stance.
- Privilege Escalation Vectors (Project IAM Admin takeover, Config Connector `roles/owner` escalation).
- Master Hardening Checklist.

## Step 4: Google Doc Generation Trigger
Execute the Google Doc generation script:
`${ANALYSIS_DIR}/generate.sh <YYYY-MM-DD>`
Report the output Google Doc URL to the user.
