# Skills & Autonomy

## Skill Supply Chain

### Provenance and Integrity

Skills are loaded from `agents/platform/skills/` at Docker build time (`COPY agents/platform/skills/ /opt/hermes/skills/`). There is **no skill provenance verification** ([SKILL-003]):
- No signature verification on SKILL.md files
- No `sync-upstream-skills` mechanism exists (referenced in the design but not implemented)
- No integrity checking at agent startup
- No checksum validation against a known-good manifest

A supply-chain compromise of the skill files at build time or of the container image registry would load attacker-controlled procedures into the agent with no detection.

### In-Pod Script Execution ([SKILL-004], High)

The agent has unrestricted shell access via the `hermes-cli` terminal toolset. Through MCP tools, it can:
- Execute arbitrary `kubectl` commands against any cluster (via `switch_kube_context` + kubeconfig generation)
- Run `gcloud` commands with its GCP service account identity
- Execute `gh` CLI commands with its GitHub installation token
- Run `hermes` CLI for notifications and agent management

The `submit-suggestion` script (`submit_suggestion.py`) uses `git push -f` (force push) to push branches ([SKILL-006]). It protects `main`, `master`, and `production`, but force-pushes to all other branches — potentially overwriting reviewer commits or destroying CI state on shared branches.

## Cron-Driven Autonomy

### Job Inventory ([SKILL-001], High)

Ten cron jobs are defined in `agents/platform/cron/jobs.json`, all `enabled: true`:

| Job | Schedule | Autonomy Level | Mutating? |
|---|---|---|---|
| github-issue-resolver | Every minute | Autonomous resolution (claim, investigate, close, comment) | Yes (GitHub writes) |
| policy-propagation | Every hour | Read + submit-suggestion PR | Yes (GitOps PR) |
| global-capacity-orchestrator | Every hour | Read + PR | Yes (GitOps PR) |
| blueprint-sync | Daily 9am | Read + submit-suggestion PR | Yes (GitOps PR) |
| fleet-wide-cost-analysis | Daily 10am | Read + report | No |
| security-patch-orchestrator | Daily 11am | Read + submit-suggestion PR | Yes (GitOps PR) |
| obtainability-audit | Daily 12pm | Read + PR | Yes (GitOps PR) |
| compliance-audit | Weekly Sunday | Read + report | No |
| standardization-validator | Weekly Sunday | Read + report | No |
| lifecycle-deprecation-manager | Monthly | Read + notify | No |

All cron jobs execute with `cron_mode: approve` (`config.yaml:44`) — **zero human approval gate** for any cron-triggered tool call.

### github-issue-resolver ([SKILL-002], High)

The most autonomous job: runs every minute, polls unaddressed GitHub issues, sorts by lowest number (no risk prioritization), claims the issue, investigates, resolves, closes, and posts comments — all without human review. This is also the primary prompt injection surface (see Prompt Injection tab).

## Human-in-the-Loop Boundaries

### What runs unattended
- All 10 cron jobs (auto-approved)
- SOUL.md "proceed autonomously" — any action where the agent judges the human would say "yes"
- Loop-Until-Done recovery — up to 5 iterations or 10 minutes per blocker without human intervention ([SKILL-007])
- GitHub issue resolution (claim → investigate → close without approval)
- GitOps PR creation (submit-suggestion)

### What requires a human gate
- "Destructive or irreversible operations" — cluster deletion, tenant offboarding, broad IAM revocation, project-level changes
- The agent is instructed to ask before these, but the distinction between "destructive" (gated) and "non-destructive" (autonomous) is **self-judged by the agent** ([SKILL-005])

### Boundary assessment

The human-gate boundaries are stated in SOUL.md but have significant gaps:
1. **Expansive autonomy rule**: "If the expected user response would simply be 'yes', do not ask" — interprets silence as consent
2. **Self-judged classification**: The agent decides what is "destructive" vs. "non-destructive"
3. **No technical enforcement**: The gate exists only in the system prompt, not in tool-level authorization — any prompt injection that overrides the system prompt removes the gate
4. **Cron bypass**: Cron jobs skip even the system-prompt-level gate via `cron_mode: approve`
5. **No second factor**: No requirement for a second human reviewer on high-impact changes (PR merge, cluster modification)
