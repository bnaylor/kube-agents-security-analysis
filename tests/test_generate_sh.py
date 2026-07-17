from pathlib import Path


def test_generate_sh_consumes_manifest():
    sh = Path("generate.sh").read_text(encoding="utf-8")
    # drives tabs from the canonical manifest
    assert "python3 -m tools.tabs" in sh
    # exactly one create_tab invocation remains (inside the loop), not 13 literals
    assert sh.count('create_tab "${url}"') == 1
    # old per-tab filename literals are gone
    assert "yolo_security_synthesis" not in sh
    assert 'threat_model.md" "Threat Model"' not in sh
