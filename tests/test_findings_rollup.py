from tools.findings_rollup import render_findings, main

F = [
    {"id": "SEC-003", "tab": "secrets_token_brokering", "statement": "key leak",
     "severity": "Critical", "evidence": "role.yaml:42", "tracking": "UNTRACKED"},
    {"id": "NET-001", "tab": "runtime_hardening_network", "statement": "open egress",
     "severity": "Medium", "evidence": "np.yaml:1", "tracking": "UNTRACKED"},
    {"id": "ARCH-001", "tab": "architectural_summary", "statement": "single-agent model",
     "severity": "Info", "evidence": "agents/", "tracking": "UNTRACKED"},
]


def test_summary_counts():
    out = render_findings(F)
    assert "**3 findings**" in out
    assert "1 Critical" in out and "1 Medium" in out and "1 Info" in out


def test_severity_sort_critical_before_medium():
    out = render_findings(F)
    assert out.index("SEC-003") < out.index("NET-001")


def test_info_is_separated():
    out = render_findings(F)
    assert "## Action items" in out and "## Informational" in out
    assert out.index("SEC-003") < out.index("## Informational")   # action items above
    assert out.index("## Informational") < out.index("ARCH-001")  # Info below the header


def test_domain_title_mapping_and_fallback():
    out = render_findings([
        {"id": "X", "tab": "secrets_token_brokering", "statement": "s",
         "severity": "High", "evidence": "e", "tracking": "t"},
        {"id": "Y", "tab": "unknown_tab", "statement": "s",
         "severity": "High", "evidence": "e", "tracking": "t"},
    ])
    assert "Secrets & Token Brokering" in out   # mapped from the manifest
    assert "unknown_tab" in out                 # fallback to raw tab


def test_cell_escapes_pipe_and_newline():
    out = render_findings([{"id": "P", "tab": "threat_model", "statement": "a|b\nc",
                            "severity": "High", "evidence": "e", "tracking": "t"}])
    row = [ln for ln in out.splitlines() if ln.startswith("| P ")][0]
    assert "a\\|b c" in row     # pipe escaped, newline collapsed -> still one row


def test_empty_findings():
    out = render_findings([])
    assert "**0 findings**" in out and "No findings recorded" in out


def test_main_writes_findings(tmp_path):
    run = tmp_path / "2026-07-16"; run.mkdir()
    (run / "audit_state.json").write_text(
        '{"generated_at":"2026-07-16","kube_agents_ref":"x",'
        '"install_namespace":"kubeagents-system","agents":["platform"],'
        '"findings":[{"id":"SEC-003","tab":"secrets_token_brokering","statement":"key leak",'
        '"severity":"Critical","evidence":"role.yaml:42","tracking":"UNTRACKED"}]}',
        encoding="utf-8")
    assert main(["2026-07-16", str(tmp_path)]) == 0
    md = (run / "findings.md").read_text(encoding="utf-8")
    assert "SEC-003" in md and "## Action items" in md


def test_main_missing_state_writes_note(tmp_path):
    run = tmp_path / "2026-07-16"; run.mkdir()
    assert main(["2026-07-16", str(tmp_path)]) == 0
    assert "No `audit_state.json`" in (run / "findings.md").read_text(encoding="utf-8")


def test_no_tracking_column():
    out = render_findings(F)
    header = [ln for ln in out.splitlines() if ln.startswith("| ID ")][0]
    assert "Tracking" not in header
    assert header.count("|") == 6  # 5 columns -> 6 pipes
