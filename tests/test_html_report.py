import tools.html_report as hr
from tools.html_report import render_tab


def test_build_report_structure(tmp_path, monkeypatch):
    monkeypatch.setattr(hr, "_load_asset",
                        lambda n: "MERMAIDJS" if n == "mermaid.min.js" else "CSSRULES")
    (tmp_path / "whats_changed.md").write_text("# Changed\n", encoding="utf-8")
    tabs = [("whats_changed.md", "What's Changed"), ("threat_model.md", "Threat Model")]
    out = hr.build_report(tmp_path, tabs)
    assert "What's Changed" in out and "Threat Model" in out   # both in the sidebar
    assert "MERMAIDJS" in out and "CSSRULES" in out            # assets inlined
    assert 'class="nav-item active"' in out                    # first tab active
    assert "Not generated this run" in out                     # missing threat_model.md -> placeholder
    assert "<h1>Changed</h1>" in out                           # rendered tab body


def test_render_table():
    md = "| a | b |\n| :-- | :-- |\n| 1 | 2 |\n"
    assert "<table>" in render_tab(md)


def test_render_fenced_code():
    out = render_tab("```python\nx = 1\n```\n")
    assert "<pre>" in out and "x = 1" in out


def test_render_mermaid_stays_escaped_for_browser():
    # Mermaid content must stay HTML-ESCAPED inside <pre class="mermaid">: the
    # browser must NOT parse tags like <br/> in the diagram (it would consume
    # them before mermaid reads .textContent). textContent decodes the entities
    # back to the literal chars mermaid needs (`<br/>`, `-->`).
    out = render_tab('```mermaid\ngraph TD\n  A["x<br/>y"] --> B\n```\n')
    assert 'class="mermaid"' in out
    assert "&lt;br/&gt;" in out       # kept escaped — browser won't parse it as a tag
    assert "<br/>" not in out         # no literal tag leaks into the <pre>
    assert "--&gt;" in out            # arrow kept escaped (textContent decodes to -->)


def test_strips_frontmatter_and_comments():
    out = render_tab("---\nonedoc_gdoc_url: REDACTED\n---\n<!-- guidance -->\n# Title\n")
    assert "onedoc_gdoc_url" not in out
    assert "guidance" not in out
    assert "<h1>Title</h1>" in out


def test_main_writes_report(tmp_path, monkeypatch):
    monkeypatch.setattr(hr, "_load_asset", lambda n: "X")
    run = tmp_path / "2026-07-16"
    run.mkdir()
    (run / "whats_changed.md").write_text("# Hi\n", encoding="utf-8")
    assert hr.main(["2026-07-16", str(tmp_path)]) == 0
    report = run / "report.html"
    assert report.exists()
    assert "Hi" in report.read_text(encoding="utf-8")


def test_main_missing_run_dir(tmp_path):
    assert hr.main(["2099-01-01", str(tmp_path)]) == 1
