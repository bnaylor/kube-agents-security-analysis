---
onedoc_gdoc_url: REDACTED-GDOC-URL
onedoc_md_file_id: REDACTED
onedoc_tab_id: REDACTED
---
---
---
# Security Analysis: GitHub Token Broker (Minty) Integration

This document analyzes the Git authentication and token brokering architecture in `kube-agents`, detailing how the Platform Agent obtains repository access while maintaining zero static secrets on persistent volumes.

---

## 1. Zero-Exposure Token Architecture

The `kube-agents` harness uses the **GitHub Token Broker (Minty)** ([abcxyz/github-token-minter](https://github.com/abcxyz/github-token-minter)) to manage Git repository access.

```
[Platform Agent Pod] ──(OIDC Token)──> [Minty Broker] ──(KMS Sign)──> [GitHub API]
```

### Key Security Properties:
1. **No Static Private Keys in Pods**: The master GitHub App private key PEM file is never stored in Kubernetes secrets or mounted into agent containers. It resides exclusively inside **GCP KMS**. Minty delegates all RSA signing operations to GCP KMS via the `AsymmetricSign` API.
2. **Short-Lived Installation Tokens**: The Platform Agent receives 1-hour, repository-scoped installation tokens (`ghs_...`) dynamically when executing GitOps workflows (`submit-suggestion` skill).
3. **Strict File Permissions**: When the agent retrieves a token from Minty via `./scripts/github_token_refresh.py`, it writes the credential to `~/.git-credentials` using strict owner-only file modes (`0600`).
4. **OIDC Claim Verification**: Minty validates the agent's projected Kubernetes ServiceAccount token (`/var/run/secrets/kubernetes.io/serviceaccount/token`) against a CEL authorization rule before issuing tokens.

---

## 2. Token Refresh Script Workflow

The token refresher script ([github_token_refresh.py](agents/platform/scripts/github_token_refresh.py)) performs the following sequence:

1. **Reads Projected K8s Token**: Reads the pod's service account OIDC JWT token.
2. **Resolves Target Repository**: Parses `remote.origin.url` from git config, or accepts `<owner>/<repo>` positional arguments.
3. **Calls Minty Endpoint**: Sends an HTTP POST to `TOKEN_BROKER_URL` (`http://github-token-minter.agent-system.svc.cluster.local:8080/token`) with headers `X-OIDC-Token: <OIDC_JWT>`.
4. **Caches Credential**: Writes `https://x-access-token:<TOKEN>@github.com` to `~/.git-credentials` (`0600`) and logs into `gh` CLI (`gh auth login --with-token`).

---

## 3. Minty CEL Policy & Hardening

Minty's access policy is configured via ConfigMap ([integrations/github/configmap.yaml](integrations/github/README.md#L158)). 

### Security Verification Rule:
Ensure that Minty's CEL rule strictly verifies both the **OIDC Issuer** (matching the GKE cluster) and the **ServiceAccount Subject**:

```yaml
version: 'minty.abcxyz.dev/v2'
rule:
  if: "assertion.iss == 'https://container.googleapis.com/v1/projects/YOUR_PROJECT_ID/locations/YOUR_REGION/clusters/YOUR_CLUSTER'"
scope:
  platform-agent-scope:
    rule:
      if: "assertion.sub == 'system:serviceaccount:kubeagents-system:platform-agent'"
    repositories:
      - 'YOUR_GITHUB_REPO'
    permissions:
      contents: 'write'
      pull_requests: 'write'
```

### Hardening Recommendations:
* **Scope Token Permissions**: For the **Read-Only Advisor Scenario**, configure Minty to issue tokens with `contents: read` and `pull_requests: write` on non-main branches, preventing direct commits to production branches.
* **Audit Trail**: Enable Cloud Logging on the Minty service to track all token generation requests, linking GitHub commit activity back to specific GKE ServiceAccount identities.
