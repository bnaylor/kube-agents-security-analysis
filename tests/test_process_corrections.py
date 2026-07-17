from tools.process_corrections import find_unparsed, process, main

SAMPLE = '''- author: Reviewer
  target: Secrets — "no raw LLM keys"
  correction: The agent can read Secrets in kubeagents-system.
'''


def test_find_unparsed_clean_inbox_is_empty():
    assert find_unparsed(SAMPLE) == []


def test_find_unparsed_flags_orphan_preamble():
    assert find_unparsed("random note\n" + SAMPLE) == ["random note"]


def test_find_unparsed_flags_unrecognized_key():
    bad = "- author: R\n  taget: typo-key line\n"   # 'taget' is not a real key
    assert "  taget: typo-key line" in find_unparsed(bad)


def test_find_unparsed_accepts_nonindented_continuation():
    # parse_inbox folds a non-indented line into the correction value, so it
    # must NOT be reported as unparsed (else it re-ingests as a duplicate).
    text = "- author: R\n  target: T\n  correction: first\nsecond line no indent\n"
    assert find_unparsed(text) == []


def test_find_unparsed_accepts_continuation_after_blank():
    # A blank line does not end a target/correction value in parse_inbox.
    text = "- author: R\n  correction: first\n\n  continued after blank\n"
    assert find_unparsed(text) == []


def test_process_creates_open_entry_and_renders_tab():
    r = process(SAMPLE, [], "2026-07-16")
    assert len(r.new_items) == 1 and r.new_items[0].status == "open"
    assert "C-001" in r.corrections_md and "Active" in r.corrections_md
    assert r.unparsed == []


def test_process_reports_unparsed():
    r = process("orphan line\n" + SAMPLE, [], "2026-07-16")
    assert r.unparsed == ["orphan line"]


def test_main_rewrites_inbox_to_unparsed_only(tmp_path):
    corr = tmp_path / "corrections"; corr.mkdir()
    (corr / "inbox.md").write_text("orphan line\n" + SAMPLE, encoding="utf-8")
    rc = main(["2026-07-16", str(tmp_path)])
    assert rc == 1                                   # unparsed content present
    assert (corr / "inbox.md").read_text().strip() == "orphan line"   # preserved, not lost
    assert (tmp_path / "2026-07-16" / "corrections_feedback.md").exists()
    assert (corr / "ledger.md").exists()   # persistent full rendered view (spec §5.1)
    # ledger got the parsed entry
    from tools.ledger import load_ledger
    assert len(load_ledger(corr / "ledger.jsonl")) == 1
