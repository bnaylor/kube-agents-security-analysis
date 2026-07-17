import json
from tools.whats_changed import previous_run_dir, assemble


def _mk(d, files):
    d.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (d / name).write_text(content, encoding="utf-8")


def test_previous_run_dir_picks_latest_before_today(tmp_path):
    for name in ("2026-07-14", "2026-07-15", "2026-07-16"):
        (tmp_path / name).mkdir()
    assert previous_run_dir(tmp_path, "2026-07-16") == tmp_path / "2026-07-15"


def test_previous_run_dir_none_on_first_run(tmp_path):
    (tmp_path / "2026-07-16").mkdir()
    assert previous_run_dir(tmp_path, "2026-07-16") is None


def test_previous_run_dir_ignores_non_date_dirs(tmp_path):
    (tmp_path / "corrections").mkdir()
    (tmp_path / "2026-07-15").mkdir()
    assert previous_run_dir(tmp_path, "2026-07-16") == tmp_path / "2026-07-15"


def test_assemble_reports_dir_and_findings_delta(tmp_path):
    prev = tmp_path / "2026-07-15"
    cur = tmp_path / "2026-07-16"
    _mk(prev, {"report.md": "old\n",
               "audit_state.json": json.dumps({"findings": [{"id": "F-1", "statement": "x"}]})})
    _mk(cur, {"report.md": "new\n",
              "audit_state.json": json.dumps({"findings": [{"id": "F-2", "statement": "y"}]})})
    r = assemble(prev, cur)
    assert r["previous"] == "2026-07-15" and r["current"] == "2026-07-16"
    assert "report.md" in r["dir_diff"]
    assert [f["id"] for f in r["findings"]["added"]] == ["F-2"]
    assert [f["id"] for f in r["findings"]["removed"]] == ["F-1"]


def test_assemble_tolerates_missing_audit_state(tmp_path):
    prev = tmp_path / "2026-07-15"
    cur = tmp_path / "2026-07-16"
    _mk(prev, {"report.md": "old\n"})
    _mk(cur, {"report.md": "new\n"})
    r = assemble(prev, cur)
    assert r["findings"] == {"added": [], "removed": [], "changed": []}
