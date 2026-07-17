# Runtime Hardening & Network

## Pod Sandboxing (gVisor)

gVisor sandboxing is **optional and off by default** ([RUNTIME-002], High). The provisioning script `provision_01a_gvisor_nodepool.sh` only creates a gVisor node pool if `ENABLE_GVISOR` is explicitly set (defaults to `false`). When enabled, it provisions a dedicated `gvisor-pool` node pool with `--sandbox=type=gvisor` on `cos_containerd`.

The PlatformAgent CRD spec includes an optional `runtimeClassName` field (`common_types.go:109-112`). The controller validates that the specified RuntimeClass exists and sets the Deployment status to "Degraded" if it doesn't — but does **not enforce** that a RuntimeClass is set. If the field is left empty, the agent pod runs on the default node pool with no kernel-level sandbox isolation.

**Risk**: Without gVisor (or an equivalent sandbox), a container escape in the LLM agent pod has direct access to the host kernel. Given the agent processes untrusted input (pod logs, GitHub issues) and executes LLM-generated code, this is a meaningful defense-in-depth gap.

## Workload Hardening

### Agent Pod SecurityContext ([RUNTIME-003], Info)

**Pod-level** (`platformagent_manifests.go:531-537`):
- `RunAsNonRoot: true`
- `RunAsUser: 10000`
- `FSGroup: 10000`
- `SeccompProfile: RuntimeDefault`

**Container-level** (`platformagent_manifests.go:598-603`):
- `AllowPrivilegeEscalation: false`
- `Capabilities.Drop: ["ALL"]`

**Assessment**: The baseline is solid — non-root user, seccomp enabled, all capabilities dropped, no privilege escalation. Gaps:
- No `ReadOnlyRootFilesystem: true` ([RUNTIME-007]) — the agent needs `/opt/data` writable, but the OS root partition could be mounted read-only
- No custom seccomp profile — `RuntimeDefault` is good but a custom profile could restrict syscalls further
- No AppArmor or SELinux profile

### Operator Pod ([RUNTIME-004], Info)
The operator pod has stronger defaults than the agent:
- `readOnlyRootFilesystem: true`
- `runAsNonRoot: true`
- `allowPrivilegeEscalation: false`
- `capabilities.drop: ["ALL"]`
- `seccompProfile: RuntimeDefault`

### LiteLLM Gateway and GitHub Token Minter
Both sub-components have well-defined NetworkPolicies with restrictive egress rules ([RUNTIME-005]):
- **LiteLLM**: Egress restricted to DNS (kube-dns, node-local-dns, metadata IPs) + HTTPS to 0.0.0.0/0 excluding RFC1918 + HTTP to metadata IP + OTel collector
- **Minty**: Ingress restricted to pods with `app: platform-agent` on port 8080; Egress: DNS + HTTPS to 0.0.0.0/0

## Network Segmentation & Egress

### Critical Gap: No Agent NetworkPolicy ([RUNTIME-001], Critical)

The platform agent pod — the **most privileged workload** in the system — has **no NetworkPolicy**. The operator does not generate one. The `deploy/` directory contains no agent NetworkPolicy. The agent has:
- **Unrestricted egress**: Can connect to any external IP, any internal service, and cloud metadata endpoints
- **Unrestricted ingress**: Any pod in the cluster can reach the agent's API server on port 8642

**What the agent can reach (and should be restricted)**:
- GCP metadata endpoint (169.254.169.254) — allows credential extraction
- Arbitrary external hosts — data exfiltration path
- Other cluster services — lateral movement

**What the agent needs to reach**:
- OTel collector (gke-managed-otel namespace)
- GitHub Token Minter (localhost or cluster service)
- LiteLLM gateway (localhost or cluster service)
- GKE API (`container.googleapis.com`)
- GitHub API (`api.github.com`)
- GCP APIs (logging, monitoring, KMS, Pub/Sub)
- DNS (kube-dns)

### Full gcloud CLI in Agent Image ([RUNTIME-006], Medium)

The Dockerfile installs `google-cloud-cli` and `google-cloud-cli-gke-gcloud-auth-plugin`, giving the agent direct access to the full GCP CLI with its Workload Identity credentials. Combined with unrestricted egress, the agent can access any GCP API without restriction.

### Ironic Default-Deny Asset

The `gke-workload-security` skill includes a `default-deny-netpol.yaml` asset that the agent can deploy to **other** namespaces — but the agent's own namespace has no such policy.
