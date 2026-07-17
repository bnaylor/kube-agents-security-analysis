# Secrets & Token Brokering

## GitHub Token Broker (Minty) Architecture

The GitHub token brokering system is well-designed and follows security best practices ([SEC-003]):

```
Agent pod → gcloud auth print-identity-token (OIDC) → Minty server (cluster-local)
  → validates OIDC token audience + issuer + GSA email
  → signs JWT via Cloud KMS (AsymmetricSign)
  → exchanges JWT for GitHub App installation token
  → returns short-lived token (1 hour) with repo-scoped permissions
```

**Authorization rules** (`configmap.yaml.template`):
- OIDC issuer allowlist: `https://accounts.google.com` only
- GSA email allowlist: specific platform agent GSA
- Token scopes: `contents:write`, `pull_requests:write` on the target repository

**Minty deployment security**:
- Runs as non-root with readOnlyRootFilesystem
- NetworkPolicy restricts ingress to pods with `app: platform-agent` on port 8080
- Egress: DNS + HTTPS to 0.0.0.0/0

**Token refresh client** (`github_token_refresh.py`):
- Automatically invoked when git operations fail (SOUL.md:40-43)
- First attempts audience-scoped OIDC token
- **Gap** ([SEC-004]): Falls back to un-scoped OIDC token on failure, removing audience restriction

## KMS-Only Signing

The Minty server uses GCP Cloud KMS for JWT signing — no static private keys exist in pods or on disk. The KMS key is project-scoped and the Minter GSA holds only `roles/cloudkms.signerVerifier` on that specific key ([LP-005]).

**CI pipeline exposure** ([SEC-005]): During staging redeploy, the GitHub App private key PEM is materialized to `/tmp/` on the CI runner for KMS import. GitHub Actions ephemeral runner cleanup mitigates this, but the key exists on disk for the duration of the import step.

## OIDC Claim Validation (CEL)

The Minty config uses Common Expression Language (CEL) for OIDC claim validation:
- `claims.iss == 'https://accounts.google.com'`
- `claims.email == '<platform-agent-gsa-email>'`
- `claims.aud == '<token-broker-url>'`

These are compile-time constants in the ConfigMap template — well-constrained.

## Short-Lived Scoped Tokens & 0600 Credential Caching

- GitHub installation tokens: 1-hour TTL, auto-refreshed by the agent
- Token cached in `gh` CLI credential store (agent pod filesystem, mode 0600 equivalent via UID 10000)
- No long-lived GitHub credentials in the agent pod

## Other Secret Handling

### API Keys in Kubernetes Secrets ([SEC-001])
All LLM provider API keys stored in `platform-agent-secrets` Secret in `kubeagents-system` namespace:
- `GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`
- `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`
- `API_SERVER_KEY` (auto-generated via `openssl rand -hex 16` if not provided — [SEC-006])

**Gap**: Unused provider keys saved as literal string `"placeholder"` rather than empty — Secret always contains non-empty values for all providers.

**Gap**: LiteLLM reads API keys as environment variables — accessible from `/proc` and potentially leaked in debug logs.

### Plaintext vars.sh ([SEC-002])
The provisioning scripts (`common.sh:save_var()`) persist all variables including API keys to `vars.sh` on the provisioning machine. While not tracked in git, this file persists on disk after provisioning and has no `.gitignore` entry.

### API_SERVER_KEY ([SEC-006])
- Auto-generated: `openssl rand -hex 16` (128-bit, cryptographically sound)
- Used as shared secret for inter-agent `call_agent` authentication
- Stored in K8s Secret and passed as env var to agent + MCP servers
- **Critical gap**: Falls back to literal `"none"` if env var unset (see Tools, MCP & Inter-Agent Trust tab)
