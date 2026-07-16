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


def test_report_md_lists_failures(tmp_path):
    result = run_preflight(tmp_path, [Check("file", "missing.yaml", "needed")])
    assert result.ok is False
    md = result.report_md()
    assert "missing.yaml" in md and "needed" in md
