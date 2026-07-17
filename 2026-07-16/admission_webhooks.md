# Admission Control (Webhooks)

## Webhook Inventory & Validation Logic

The kube-agents operator registers **two admission webhooks** for the `PlatformAgent` CRD:

### Mutating Webhook (`/mutate-kubeagents-x-k8s-io-v1alpha1-platformagent`)
- `failurePolicy: Fail`
- Triggers: CREATE, UPDATE
- **Current state**: TODO stub ([ADM-004]) — logs the call but performs no defaulting logic
- CRD schema-level defaults (ImagePullPolicy, DashboardEnabled) are the only defaults in effect

### Validating Webhook (`/validate-kubeagents-x-k8s-io-v1alpha1-platformagent`)
- `failurePolicy: Fail`
- Triggers: CREATE, UPDATE, DELETE
- **Two checks performed**:

**Check 1 — Cluster-level cardinality** (lines 116-134):
- Lists ALL PlatformAgent CRs cluster-wide
- Rejects creation if any non-terminating PlatformAgent with a different name or namespace exists
- Skips terminating agents to prevent deletion deadlocks
- Enforces exactly one PlatformAgent per cluster

**Check 2 — Global GCS lock** (lines 137-172):
- Reads lock object from GCS bucket `{projectID}-kube-agents-lock/platform-agent-lock.json`
- Rejects if lock exists with different clusterName, agentName, or namespace
- Lock absence is treated as "no lock exists" (permissive on first creation)
- Requires `spec.harness.projectId` and `spec.harness.clusterName` to be set

Both webhooks use `failurePolicy: Fail` ([ADM-005]) — a webhook outage blocks all PlatformAgent CREATE and UPDATE operations. This is a security-over-availability trade-off that prevents circumvention by DoS-ing the webhook.

## Identified Gaps

### No Security Posture Validation ([ADM-001], High)
The webhook validates **only** cardinality — it does not validate any security properties of the CR spec:
- `spec.deployment.runtimeClassName` — no check that it references a secure runtime (gVisor)
- `spec.deployment.initContainers` — arbitrary containers can run before the agent
- `spec.deployment.sidecars` — arbitrary sidecars alongside the agent
- `spec.deployment.env` — no restrictions on environment variables; can override `API_SERVER_KEY`
- `spec.deployment.extraVolumes` — arbitrary host path or secret mounts
- `spec.security.serviceAccountName` — any SA can be used, including cluster-admin
- `spec.security.serviceAccountAnnotations` — any GCP Workload Identity binding
- Container capabilities, privilege escalation, or hostNetwork in user-supplied containers

A user with PlatformAgent CRD create/update access can configure the agent to run with escalated privileges via sidecars, init containers, or custom ServiceAccounts — and the webhook will admit it.

### GCS Lock Lifecycle ([ADM-002], Medium)
- The webhook is a **read-only** consumer of the GCS lock — it never creates or releases the lock
- Lock lifecycle depends on external provisioning logic (not visible in webhook code)
- A stale lock (e.g., from a destroyed cluster that didn't clean up) could permanently block new deployments
- The GCS bucket uses project-level naming (`{projectID}-kube-agents-lock`) — any principal with `storage.objects.delete` on the bucket can remove the lock

### No Deletion Validation ([ADM-003], Medium)
`ValidateDelete` is a TODO stub — any user with delete permission on PlatformAgent CRs can delete the agent without additional guard. The controller handles cleanup (removes ClusterRoleBindings, explorer ClusterRole), but there is no webhook-level check to prevent accidental or malicious deletion.

## Proposed Hardening Gates

1. **Validate RuntimeClassName**: Reject or warn if `runtimeClassName` is empty or doesn't reference a known sandboxed runtime (gVisor).

2. **Validate initContainers and sidecars**: Reject containers that:
   - Run as root or have `privileged: true`
   - Mount host paths (`hostPath` volumes)
   - Use `hostNetwork`, `hostPID`, or `hostIPC`
   - Don't drop ALL capabilities
   - Don't set `allowPrivilegeEscalation: false`

3. **Validate ServiceAccountName**: Reject SAs that have cluster-admin or similarly broad ClusterRoleBindings.

4. **Validate environment variables**: Block overrides of security-sensitive env vars (`API_SERVER_KEY`, `HERMES_HOME`).

5. **Add deletion guard**: Require an annotation or specific label (`kubeagents.x-k8s.io/allow-delete: true`) before allowing deletion.

6. **GCS lock release**: Add a lock-release mechanism (either in the webhook's `ValidateDelete` or in the controller's finalizer) to prevent stale locks from blocking future deployments.
