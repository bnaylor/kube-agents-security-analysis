from pathlib import Path


def test_mermaid_vendored():
    js = Path("tools/assets/mermaid.min.js")
    assert js.exists() and js.stat().st_size > 100_000   # mermaid.min.js is large
    assert "mermaid" in js.read_text(encoding="utf-8", errors="ignore")[:20000].lower()


def test_report_css_present():
    css = Path("tools/assets/report.css")
    assert css.exists() and css.stat().st_size > 0


def test_requirements_declares_markdown():
    assert "markdown" in Path("requirements.txt").read_text(encoding="utf-8").lower()
