import pytest
from tools.ledger import (
    Correction, transition, GuardrailError, load_ledger, save_ledger,
)


def _c(**kw):
    base = dict(id="C-001", raised="2026-07-16", author="Reviewer",
                target="Secrets — 'no raw LLM keys'", correction="can read secrets",
                status="open")
    base.update(kw)
    return Correction(**base)


def test_valid_transition_open_to_confirmed():
    c = transition(_c(), "confirmed", "2026-07-17")
    assert c.status == "confirmed"
    assert {"date": "2026-07-17", "status": "confirmed"} in c.history


def test_invalid_transition_rejected():
    with pytest.raises(ValueError):
        transition(_c(status="absorbed"), "open", "2026-07-17")


def test_deny_without_proof_is_blocked():
    with pytest.raises(GuardrailError):
        transition(_c(), "denied", "2026-07-17", proof="")


def test_deny_with_proof_allowed():
    c = transition(_c(), "denied", "2026-07-17", proof="grep shows key IS handled")
    assert c.status == "denied" and c.proof


def test_ledger_roundtrip(tmp_path):
    path = tmp_path / "ledger.jsonl"
    items = [_c(), _c(id="C-002", author="Iris")]
    save_ledger(path, items)
    loaded = load_ledger(path)
    assert [x.id for x in loaded] == ["C-001", "C-002"]
    assert loaded[1].author == "Iris"
