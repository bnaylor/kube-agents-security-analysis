import subprocess

from tools import preflight
from tools.preflight import Check, evaluate_check, run_preflight


def test_file_check_passes_when_present(tmp_path):
    (tmp_path / "config.yaml").write_text("x")
    r = evaluate_check(Check("file", "config.yaml", "cfg"), tmp_path)
    assert r.passed and not r.skipped


def test_file_check_fails_when_missing(tmp_path):
    r = evaluate_check(Check("file", "config.yaml", "cfg"), tmp_path)
    assert not r.passed


def test_dir_check_passes_when_present(tmp_path):
    (tmp_path / "agents").mkdir()
    r = evaluate_check(Check("dir", "agents", "agents dir"), tmp_path)
    assert r.passed and not r.skipped


def test_absent_check_passes_when_missing(tmp_path):
    r = evaluate_check(Check("absent", "agents/operator", "removed"), tmp_path)
    assert r.passed


def test_absent_check_fails_when_present(tmp_path):
    (tmp_path / "agents" / "operator").mkdir(parents=True)
    r = evaluate_check(Check("absent", "agents/operator", "removed"), tmp_path)
    assert not r.passed


def test_optional_command_missing_is_not_fatal(tmp_path):
    chk = Check("command", "definitely-not-a-real-binary-xyz", "opt", optional=True)
    result = run_preflight(tmp_path, [chk])
    assert result.ok is True


def test_optional_command_present_but_failing_is_not_fatal(tmp_path):
    # 'false' exists on PATH and always exits non-zero
    chk = Check("command", "false", "opt", optional=True)
    result = run_preflight(tmp_path, [chk])
    assert result.ok is True


def test_command_check_timeout_is_skipped(monkeypatch, tmp_path):
    # A command that stalls (e.g. kubectl with no cluster) must not block:
    # a timeout is treated as skipped, so an optional check stays non-fatal.
    def boom(*_a, **_k):
        raise subprocess.TimeoutExpired(cmd="x", timeout=preflight._COMMAND_TIMEOUT)
    monkeypatch.setattr(preflight.subprocess, "run", boom)
    r = evaluate_check(Check("command", "sleep 99", "opt", optional=True), tmp_path)
    assert r.skipped and not r.passed and "timed out" in r.detail
    assert run_preflight(tmp_path, [Check("command", "sleep 99", "opt", optional=True)]).ok is True


def test_report_md_lists_failures(tmp_path):
    result = run_preflight(tmp_path, [Check("file", "missing.yaml", "needed")])
    assert result.ok is False
    md = result.report_md()
    assert "missing.yaml" in md and "needed" in md
