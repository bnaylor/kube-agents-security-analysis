# Least-Privilege Inventory

## Platform Agent KSA — Kubernetes ClusterRoles

The controller creates **three RBAC objects** per PlatformAgent ([LP-001]):

### Viewer ClusterRoleBinding
Binds agent ServiceAccount → built-in Kubernetes **`view`** ClusterRole.
- **Scope**: Cluster-wide read on most resources (pods, services, deployments, configmaps, secrets metadata, endpoints, etc.)
- **Finding**: Broader than the agent's stated "standard GKE Read-Only cluster visibility" (SOUL.md:15). `view` includes secrets metadata (names only), configmaps content, and all resource configurations cluster-wide.

### Explorer ClusterRole (custom)
- `nodes`, `pods`, `namespaces` in core API group: `get, list`
- `customresourcedefinitions` in `apiextensions.k8s.io`: `get, list`

### Explorer ClusterRoleBinding
Binds agent ServiceAccount → Explorer ClusterRole.

**Static agent_rbac overlay** (`config/agent_rbac/platformagent.yaml`) ([LP-002]):
- CRUD on KCC `containerclusters` (GKE cluster create/delete via Config Connector)
- Read on `apps/*`, `batch/*`, `networking.k8s.io/*`
- Full CRUD on `kubeagents.x-k8s.io/*` (self-modifying CRD capability)

**Operator's own ClusterRole** ([LP-004], Critical):
- `bind` verb on `clusterroles` and `clusterrolebindings` — can grant any ClusterRole to any subject
- Full CRUD on Deployments, ServiceAccounts, PVCs, ConfigMaps, Services
- Read on nodes, namespaces, pods, events, PVs, CRDs, RuntimeClasses

## Platform Agent GSA — GCP IAM Roles

From `k8s-operator/scripts/provision_03_gcp_iam.sh` ([LP-003]):

### Default: `gke-admin` permission set
| Role | Scope |
|---|---|
| `roles/container.clusterAdmin` | Full GKE cluster management |
| `roles/container.admin` | GKE cluster administration |
| `roles/monitoring.admin` | Full monitoring configuration access |
| `roles/logging.viewer` | Read logs (not admin — deliberately downgraded from legacy) |
| `roles/iam.serviceAccountUser` | Impersonate any SA in the project |
| `roles/iam.securityReviewer` | Read all IAM policies |
| `roles/mcp.toolUser` | Custom: MCP tool usage |

### Alternative: `read-only` permission set
| Role | Scope |
|---|---|
| `roles/container.clusterViewer` | Read-only GKE cluster view |
| `roles/container.viewer` | Read-only container resources |
| `roles/monitoring.viewer` | Read-only monitoring |
| `roles/logging.viewer` | Read logs |
| `roles/iam.serviceAccountUser` | Impersonate SAs |
| `roles/iam.securityReviewer` | Read IAM policies |
| `roles/mcp.toolUser` | Custom: MCP tool usage |

### GitHub Token Minter GSA ([LP-005])
- `roles/cloudkms.signerVerifier` on the specific KMS key only
- **No project-level IAM roles** — well-scoped

### GChat PubSub ([LP-006])
- `roles/pubsub.subscriber` + `roles/pubsub.viewer` on a single subscription — well-scoped

## Config Connector / KCC Roles

The static agent_rbac grants the agent KSA CRUD on `container.cnrm.cloud.google.com/containerclusters` within the `kubeagents-system` namespace. This allows the agent to create, modify, and delete GKE cluster resources via Config Connector custom resources. In gke-admin mode, the GSA's `container.clusterAdmin` IAM role makes these KCC operations effective.

## Minimality Assessment & Excess

| Permission | Minimal? | Excess |
|---|---|---|
| K8s `view` ClusterRole | **No** | Agent does not need secrets metadata, configmaps content, or endpoint visibility cluster-wide. A namespaced Role with targeted resource access would be sufficient. |
| Explorer ClusterRole | **Mostly** | `get/list` on nodes, pods, namespaces, CRDs aligns with fleet auditing. Could be namespaced. |
| Static agent_rbac `containerclusters` CRUD | **No** | KCC cluster CRUD is operational, not read-only. Should be scoped behind the GitOps workflow rather than direct KCC access. |
| Static agent_rbac CRUD on own CRD | **No** | Self-modifying CRD capability. Agent should not be able to modify its own deployment spec. |
| GCP `container.clusterAdmin` (default) | **No** | Default should be `read-only`; gke-admin should be opt-in with explicit justification. |
| GCP `iam.serviceAccountUser` | **Debatable** | Needed for Workload Identity, but allows impersonation of any SA in the project. |
| GCP `monitoring.admin` (default) | **No** | `monitoring.viewer` is sufficient for fleet auditing. Admin is only needed if the agent creates/modifies monitoring config (which it shouldn't do directly outside GitOps). |
| GitHub Token Minter GSA | **Yes** | Single KMS key, signerVerifier only. |
| Operator `bind` on ClusterRoles | **No** | `bind` is needed for the operator to create ClusterRoleBindings for the agent, but the operator could use an escrow pattern (pre-defined ClusterRoles, only bind those) rather than unrestricted `bind`. |
