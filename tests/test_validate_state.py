from tools.validate_state import validate_state


def _valid():
    return {
        "generated_at": "2026-07-16",
        "kube_agents_ref": "abc1234",
        "install_namespace": "kubeagents-system",
        "agents": ["platform"],
        "findings": [
            {"id": "F-001", "tab": "Tools, MCP & Inter-Agent Trust",
             "statement": "API_SERVER_KEY defaults to 'none'",
             "severity": "high", "evidence": "agent_common_server.py:29",
             "tracking": "UNTRACKED"},
        ],
    }


def test_valid_state_has_no_errors():
    assert validate_state(_valid()) == []


def test_missing_top_key_is_error():
    data = _valid(); del data["findings"]
    errs = validate_state(data)
    assert any("findings" in e for e in errs)


def test_wrong_top_type_is_error():
    data = _valid(); data["agents"] = "platform"
    errs = validate_state(data)
    assert any("agents" in e for e in errs)


def test_finding_missing_field_is_error():
    data = _valid(); del data["findings"][0]["evidence"]
    errs = validate_state(data)
    assert any("evidence" in e for e in errs)
