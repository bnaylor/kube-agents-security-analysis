from tools.tabs import TABS, main


def test_manifest_has_13_tabs_in_order():
    assert len(TABS) == 13
    assert TABS[0] == ("whats_changed.md", "What's Changed")
    assert TABS[-1] == ("corrections_feedback.md", "Corrections & Feedback")
    names = [f for f, _ in TABS]
    assert len(set(names)) == 13
    assert all(f.endswith(".md") for f in names)


def test_main_prints_tab_lines(capsys):
    assert main([]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 13
    assert lines[0] == "whats_changed.md\tWhat's Changed"
    assert lines[-1] == "corrections_feedback.md\tCorrections & Feedback"
