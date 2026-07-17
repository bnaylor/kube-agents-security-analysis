from tools.diff_reports import diff_dirs, diff_findings


def test_diff_dirs_reports_changed_file(tmp_path):
    old = tmp_path / "old"; new = tmp_path / "new"
    old.mkdir(); new.mkdir()
    (old / "a.md").write_text("one\n")
    (new / "a.md").write_text("two\n")
    out = diff_dirs(old, new)
    assert "a.md" in out and "two" in out


def test_diff_dirs_empty_when_identical(tmp_path):
    old = tmp_path / "old"; new = tmp_path / "new"
    old.mkdir(); new.mkdir()
    (old / "a.md").write_text("same\n")
    (new / "a.md").write_text("same\n")
    assert diff_dirs(old, new) == ""


def test_diff_findings_classifies():
    old = [{"id": "F-1", "statement": "x"}, {"id": "F-2", "statement": "y"}]
    new = [{"id": "F-2", "statement": "y2"}, {"id": "F-3", "statement": "z"}]
    d = diff_findings(old, new)
    assert {f["id"] for f in d["added"]} == {"F-3"}
    assert {f["id"] for f in d["removed"]} == {"F-1"}
    assert {f["id"] for f in d["changed"]} == {"F-2"}


def test_main_handles_runtime_error(monkeypatch, capsys):
    import tools.diff_reports as dr
    def boom(_a, _b):
        raise RuntimeError("git blew up")
    monkeypatch.setattr(dr, "diff_dirs", boom)
    assert dr.main(["old", "new"]) == 1
    assert "git blew up" in capsys.readouterr().err
