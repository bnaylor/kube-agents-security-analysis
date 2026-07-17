"""Canonical 13-tab manifest for the audit report — the single source of truth
consumed by generate.sh (Google Doc) and tools.html_report (HTML)."""
from __future__ import annotations

import sys

# (filename, title) in publish order (Tab 0 first).
TABS: list[tuple[str, str]] = [
    ("whats_changed.md", "What's Changed"),
    ("findings.md", "Findings"),
    ("architectural_summary.md", "Architectural & Security Summary"),
    ("threat_model.md", "Threat Model"),
    ("least_privilege_inventory.md", "Least-Privilege Inventory"),
    ("secrets_token_brokering.md", "Secrets & Token Brokering"),
    ("agentic_prompt_injection.md", "Prompt Injection & Untrusted Input"),
    ("agentic_tools_mcp_trust.md", "Tools, MCP & Inter-Agent Trust"),
    ("agentic_skills_autonomy.md", "Skills & Autonomy"),
    ("admission_webhooks.md", "Admission Control (Webhooks)"),
    ("runtime_hardening_network.md", "Runtime Hardening & Network"),
    ("pipeline_cicd_supply_chain.md", "GitOps & CI/CD Integrity"),
    ("data_audit_detection.md", "Data, Audit & Detection"),
    ("corrections_feedback.md", "Corrections & Feedback"),
]


def main(argv: list[str] | None = None) -> int:
    for filename, title in TABS:
        sys.stdout.write(f"{filename}\t{title}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
