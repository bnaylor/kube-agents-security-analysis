# GitOps & CI/CD Integrity

## GitOps Mutation-Channel Safety

### submit-suggestion PR Flow

The agent's primary mutation channel is the `submit-suggestion` workflow:
1. Agent creates a git branch in the local clone
2. Agent commits changes
3. Agent force-pushes branch via `gh` CLI with GitHub installation token
4. Agent opens a PR

**Protected-branch guard**: The script protects `main`, `master`, and `production` from force-push, but force-pushes to all other branches ([PIPE-004]). This can overwrite reviewer commits or destroy CI state on shared feature branches.

**No auto-merge**: There is no auto-merge, merge-queue, or `merge_group` workflow trigger configured ([PIPE-007]). Humans must manually review and merge PRs. This is a positive control — every agent-authored change requires human approval before landing.

**Branch protection**: Not configurable from within this repository (branch protection rules are GitHub-side settings). The audit cannot verify whether branch protection requiring PR reviews, status checks, or signed commits is enabled on the target repository.

## Read-Only SRE Agent Write-Channel Audit

Grounded in kube-agents PR #315. Status at time of audit: the read-only SRE agent is **not yet implemented** in the audited codebase. The following is a design audit based on the PR description and the current submit-suggestion implementation:

1. **Identity separation**: PR #315 reportedly copy-pastes submit-suggestion. The SRE agent must use a **distinct GitHub App or PAT**, not the master Platform Agent identity. If it shares the Minty token, write attribution is lost — all mutations appear as the Platform Agent.

2. **No self-approval**: The SRE agent's PRs must be subject to the same branch protection rules as human PRs. The agent must not be able to approve its own PRs or bypass required reviewers.

3. **CI environment gates**: Agent-authored commits must pass the same CI checks as human commits. For an SRE agent that might propose infrastructure changes, consider requiring a human `/approve` comment before CI runs integration tests on agent-authored commits (to prevent CI resource abuse).

## GitHub Actions / Workflow Security

### No Security Scanning ([PIPE-001], High)

The CI pipeline (14 workflows) has **no security scanning** of any kind. There is no:
- **zizmor** — GitHub Actions workflow security scanner
- **trivy / grype / snyk** — container image vulnerability scanning
- **gosec** — Go security scanner
- **bandit** — Python security scanner
- **semgrep / CodeQL** — SAST
- **checkov / kubescape** — Kubernetes manifest scanning
- **hadolint / dockle** — Dockerfile linting

The only quality checks are `actionlint` (GitHub Actions syntax validation) and `prettier` (code formatting). An intentionally or accidentally malicious dependency would reach the published container image with no detection.

### Action Version Pinning ([PIPE-002], Medium)

Actions are pinned to major or minor version tags (`@v7`, `@v3`, `@v6`), not immutable commit SHAs. A malicious update to a tag-point within the resolved semver range would automatically flow into the next CI run. The `docker-publish-gcp.yml` workflow (which pushes to Artifact Registry) uses `actions/checkout@v7` and `google-github-actions/auth@v3` — both high-value targets.

### Specific Workflow Risks

- **GITHUB_OUTPUT injection** ([PIPE-005], Low): `staging-redeploy-integrations.yml` writes `github.event.inputs` values unsanitized to `$GITHUB_OUTPUT`. Requires `workflow_dispatch` access (trusted user gate).
- **pull_request_target** ([PIPE-006], Low): `auto_request_review.yml` triggers on `pull_request_target` with `pull-requests:write` permission. Classic dangerous trigger pattern, though the specific action is generally considered safe.

### Dependabot Coverage ([PIPE-003], Medium)

Dependabot is configured for `github-actions` and `docker` ecosystems only. Missing:
- **Python (pip)**: Dockerfile includes `pip install` of multiple packages with no automated update tracking
- **Node.js (npm)**: Dockerfile includes `npm install` for mcp-remote
- **Go (gomod)**: k8s-operator has a `go.mod` with no dependabot tracking

## Container Image & Dependency Provenance

- **Docker publish**: Uses `docker/build-push-action` to build and push to GCP Artifact Registry
- **Image signing**: `cosign-installer@v4.1.2` is included in the docker-publish workflow (pinned to patch version — a positive exception to the tag-pinning pattern)
- **Base images**: Dockerfile uses `ubuntu:24.04` as base image (floating tag — not pinned to digest)
- **Python packages**: Installed via `pip install` with no version pinning or requirements.txt hash checking visible in the Dockerfile
- **Go dependencies**: `go.mod` and `go.sum` provide checksum verification for operator dependencies
- **SLSA / provenance attestation**: Not configured
