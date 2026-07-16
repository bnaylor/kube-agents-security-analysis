---
onedoc_gdoc_url: REDACTED-GDOC-URL
onedoc_md_file_id: REDACTED
onedoc_tab_id: REDACTED
---
---
---
# Webhook Security Analysis: Validating Gates for PlatformAgent CRD

This document analyzes the current admission webhooks in `k8s-operator/internal/webhook/` and proposes security hardening gates for the `PlatformAgent` Custom Resource Definition (CRD).

---

## 1. Current Webhook Architecture

In the updated codebase, the operator manages a single Custom Resource Definition: `PlatformAgent` (`platformagents.kubeagents.x-k8s.io`).

The corresponding webhook handlers are defined in [platformagent_webhook.go](file://k8s-operator/internal/webhook/platformagent_webhook.go):
* **Mutating Webhook** (`/mutate-kubeagents-x-k8s-io-v1alpha1-platformagent`): Standard Kubebuilder defaulter scaffolding.
* **Validating Webhook** (`/validate-kubeagents-x-k8s-io-v1alpha1-platformagent`): Implements custom validation logic during `CREATE` and `UPDATE` operations.

---

## 2. Current Validation Logic Audit

The validating webhook currently enforces two cardinality constraints:

1. **Local Cardinality Gate (Cluster-Level)**:
   * Queries the K8s API reader for existing `PlatformAgent` resources in the cluster.
   * Rejects creation of a second `PlatformAgent` instance, enforcing a strict 1-agent-per-cluster policy.
   * Safely ignores terminating resources (`DeletionTimestamp != nil`).

2. **Global Cardinality Gate (GCP Project-Level)**:
   * Reads `spec.harness.projectId` and `spec.harness.clusterName`.
   * Queries Google Cloud Storage (GCS) for a project-level lock object: `${PROJECT_ID}-kube-agents-lock/platform-agent-lock.json`.
   * Rejects deployment if a `PlatformAgent` is already registered for that GCP Project ID in another GKE cluster.

---

## 3. Identified Security Gaps & Proposed Hardening Gates

While the cardinality gates prevent duplicate agent deployments, the validating webhook does not currently inspect sensitive security spec fields. If an attacker with K8s namespace access creates or updates a `PlatformAgent` CR, they could attempt to escalate privileges.

We recommend adding the following three validation gates:

### Gate 1: ServiceAccount Name & Namespace Restrictions
* **Risk**: An attacker could set `spec.security.serviceAccountName: controller` or `kubeagents-controller-manager`, causing the operator to mount the operator controller's high-privilege KSA into the agent pod.
* **Validation Check**:
  * Reject system-reserved ServiceAccounts (`default`, `controller`, `kubeagents-controller-manager`, `system`).
  * Enforce that `spec.security.serviceAccountName` (if specified) equals `agent.Name` or starts with `platform-agent-`.

### Gate 2: Workload Identity GSA Annotation Validation
* **Risk**: An attacker could inject a high-privilege GSA email into `spec.security.serviceAccountAnnotations["iam.gke.io/gcp-service-account"]` (e.g. `project-owner@...` or `controller-gsa@...`).
* **Validation Check**:
  * Reject GSA emails matching system or controller service account patterns (`*controller-gsa*`, `*owner*`).
  * Verify that the GSA email matches the expected project ID domain (`*@${PROJECT_ID}.iam.gserviceaccount.com`).

### Gate 3: Container Image & Runtime Environment Security
* **Risk**: An attacker could modify `spec.deployment.image` to run a compromised image or inject malicious environment variables.
* **Validation Check**:
  * Verify `spec.deployment.image` originates from trusted container registries (e.g. `ghcr.io/gke-labs/` or project Artifact Registry `*.pkg.dev`).
  * Sanitize custom environment variables (`spec.deployment.env`) to block overrides of sensitive framework paths like `HERMES_HOME` or `TOKEN_BROKER_URL`.

---

## 4. Draft Validation Implementation for PlatformAgent

Below is the recommended Go code snippet to add to `validatePlatformAgent` in `platformagent_webhook.go`:

```go
func (v *PlatformAgentCustomValidator) validatePlatformAgent(ctx context.Context, platformAgent *agentv1alpha1.PlatformAgent) (admission.Warnings, error) {
	if platformAgent.DeletionTimestamp != nil {
		return nil, nil
	}

	var allErrs field.ErrorList

	// 1. Cardinality Checks (Existing)
	// ... (Cluster and GCS lock checks) ...

	// 2. Security Spec Validation (Proposed)
	if platformAgent.Spec.Security != nil {
		sec := platformAgent.Spec.Security

		// Validate ServiceAccountName
		if sec.ServiceAccountName != "" {
			forbiddenSAs := map[string]bool{
				"kubeagents-controller-manager": true,
				"controller":                    true,
				"default":                       true,
				"builder":                       true,
			}
			if forbiddenSAs[sec.ServiceAccountName] {
				allErrs = append(allErrs, field.Forbidden(
					field.NewPath("spec", "security", "serviceAccountName"),
					fmt.Sprintf("binding to system service account %q is forbidden", sec.ServiceAccountName),
				))
			}
		}

		// Validate Workload Identity Annotation
		if len(sec.ServiceAccountAnnotations) > 0 {
			if gsaEmail, exists := sec.ServiceAccountAnnotations["iam.gke.io/gcp-service-account"]; exists {
				if strings.Contains(gsaEmail, "controller-gsa") || strings.Contains(gsaEmail, "admin") {
					allErrs = append(allErrs, field.Forbidden(
						field.NewPath("spec", "security", "serviceAccountAnnotations"),
						"binding to privileged system GSA is forbidden",
					))
				}
			}
		}
	}

	if len(allErrs) > 0 {
		return nil, apierrors.NewInvalid(
			schema.GroupKind{Group: "kubeagents.x-k8s.io", Kind: "PlatformAgent"},
			platformAgent.Name,
			allErrs,
		)
	}

	return nil, nil
}
```
