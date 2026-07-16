from tools.ledger import Correction, parse_inbox, next_id, ingest_inbox

SAMPLE = """- author: Reviewer
  target: Secrets & Token Brokering — "Agents do not handle raw LLM keys"
  correction: The agent has access to the kubeagents-system namespace and can
    read ConfigMaps/Secrets that contain LLM API keys.
"""


def test_parse_inbox_single_entry():
    entries = parse_inbox(SAMPLE)
    assert len(entries) == 1
    e = entries[0]
    assert e.author == "Reviewer"
    assert "Agents do not handle raw LLM keys" in e.target
    assert "read ConfigMaps/Secrets" in e.correction


def test_next_id_increments():
    assert next_id([]) == "C-001"
    assert next_id([Correction("C-004", "d", "a", "t", "c", "open")]) == "C-005"


def test_ingest_creates_open_and_clears_inbox():
    new, remaining = ingest_inbox(SAMPLE, [], "2026-07-16")
    assert len(new) == 1
    assert new[0].status == "open"
    assert new[0].id == "C-001"
    assert new[0].raised == "2026-07-16"
    assert remaining.strip() == ""


MULTI = SAMPLE + '''- author: Iris
  target: Runtime — "no gVisor"
  correction: gVisor runtimeClass is configured.
'''


def test_ingest_multiple_entries_increment_ids():
    new, remaining = ingest_inbox(MULTI, [], "2026-07-16")
    assert [c.id for c in new] == ["C-001", "C-002"]
    assert [c.author for c in new] == ["Reviewer", "Iris"]
    assert remaining.strip() == ""
