# What's Changed

## Run Summary

| | Previous (2026-07-15) | Current (2026-07-16) |
|---|---|---|
| **Format** | v1 (ad-hoc Markdown) | v2 (structured `audit_state.json` → 13 tabs) |
| **kube-agents ref** | N/A (not recorded) | `ba98365` |
| **Findings** | 6 ad-hoc analyses | 56 structured findings across 11 domains |
| **Tabs** | 6 Markdown files | 13 tabs (11 domain + What's Changed + Corrections) |

## Delta Summary

This is the **baseline v2 run**. The prior run (2026-07-15) used the v1 ad-hoc format with 6 standalone Markdown analyses covering architectural summary, threat model, least privilege (platform agent), webhook analysis, devteam token refresh, and YOLO mode synthesis. The v2 run replaces these with a formal 11-domain, 13-tab framework backed by a validated `audit_state.json` ground-truth artifact, a cross-run corrections ledger, and deterministic tool-driven diffing.

## New Findings (56 total)

All 56 findings are new in this run (no prior `audit_state.json` to diff against). They span:

| Domain | Count | Critical | High | Medium | Low | Info |
|---|---|---|---|---|---|---|
| Architectural Summary | 5 | 1 | 1 | 0 | 0 | 3 |
| Threat Model | 6 | 3 | 2 | 0 | 0 | 1 |
| Least-Privilege Inventory | 6 | 1 | 3 | 0 | 0 | 2 |
| Secrets & Token Brokering | 6 | 0 | 2 | 2 | 0 | 2 |
| Prompt Injection & Untrusted Input | 7 | 2 | 2 | 3 | 0 | 0 |
| Tools, MCP & Inter-Agent Trust | 7 | 1 | 3 | 3 | 0 | 0 |
| Skills & Autonomy | 7 | 0 | 3 | 4 | 0 | 0 |
| Admission Control (Webhooks) | 5 | 0 | 1 | 2 | 1 | 1 |
| Runtime Hardening & Network | 7 | 1 | 1 | 1 | 1 | 3 |
| GitOps & CI/CD Integrity | 7 | 0 | 1 | 3 | 2 | 1 |
| Data, Audit & Detection | 8 | 0 | 2 | 4 | 1 | 1 |

## Key Changes Since v1

- **v1 scope broadened**: The v2 run covers the full agentic attack surface (prompt injection, MCP/tools trust, skills autonomy, CI/CD supply chain, data/audit) that v1 did not address.
- **CRD security posture**: The v2 run identifies that the PlatformAgent CRD allows arbitrary initContainers, sidecars, and env vars with no webhook validation of security properties.
- **NetworkPolicy gap**: The v2 run surfaces that the agent pod has no NetworkPolicy despite being the most privileged workload.
- **API_SERVER_KEY "none" fallback**: New finding that inter-agent auth falls back to a trivially forgeable literal string.
- **Prompt injection vectors**: The v2 run systematically maps all untrusted input paths to the LLM context (pod logs, GitHub issues, CRD specs, audit logs).
- **Corrections ledger**: New cross-run mechanism for reviewer feedback tracking.

## Pre-flight Drift

No drift detected. All 5 path-hint checks passed against `kube-agents@ba98365`. One optional check skipped (kubectl not available in this environment).
