# GitOps & CI/CD Integrity

<!-- Tab 10 · Pipeline & Supply Chain. -->

## GitOps Mutation-Channel Safety
<!-- submit-suggestion PR flow; branch protection; auto-merge posture; CI injection on agent PRs. -->

## Read-Only SRE Agent Write-Channel Audit
<!-- Grounded in kube-agents PR #315 (audit the design before it lands):
     1. Identity separation — distinct GitHub App/PAT, NOT the master Platform
        Agent identity (#315 reportedly copy-pasted submit-suggestion — verify).
     2. No self-approval / no bypass of branch protection.
     3. CI environment gates — human approve-to-run before building/deploying/
        running integration tests on agent-authored commits. -->

## GitHub Actions / prow Workflow Security
<!-- Fold in existing zizmor posture. -->

## Container Image & Dependency Provenance
