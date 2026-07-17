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


def test_assemble_reports_counts_and_refs(tmp_path):
    prev = tmp_path / "2026-07-15"
    cur = tmp_path / "2026-07-16"
    _mk(prev, {"audit_state.json": json.dumps({"kube_agents_ref": "old111",
        "findings": [{"id": "F-1", "severity": "High"},
                     {"id": "F-2", "severity": "Low"}]})})
    _mk(cur, {"audit_state.json": json.dumps({"kube_agents_ref": "new222",
        "findings": [{"id": "F-3", "severity": "High"}]})})
    r = assemble(prev, cur)
    assert r["previous"] == "2026-07-15" and r["current"] == "2026-07-16"
    assert r["previous_ref"] == "old111" and r["current_ref"] == "new222"
    assert r["previous_count"] == 2 and r["current_count"] == 1
    assert r["previous_by_severity"] == {"High": 1, "Low": 1}
    assert r["current_by_severity"] == {"High": 1}
    assert "dir_diff" not in r and "findings" not in r


def test_assemble_tolerates_missing_audit_state(tmp_path):
    prev = tmp_path / "2026-07-15"
    cur = tmp_path / "2026-07-16"
    _mk(prev, {"report.md": "old\n"})
    _mk(cur, {"report.md": "new\n"})
    r = assemble(prev, cur)
    assert r["previous_count"] == 0 and r["current_count"] == 0
    assert r["previous_ref"] is None and r["current_ref"] is None
    assert r["previous_by_severity"] == {} and r["current_by_severity"] == {}
