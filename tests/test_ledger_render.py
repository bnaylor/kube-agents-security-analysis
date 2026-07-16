from tools.ledger import Correction, render_markdown


def _c(status, cid="C-001", author="Reviewer"):
    return Correction(cid, "2026-07-16", author, "Secrets — 'x'", "claim", status)


def test_render_includes_active_entry():
    md = render_markdown([_c("open")])
    assert "C-001" in md and "Reviewer" in md and "open" in md.lower()


def test_active_only_excludes_retired():
    md = render_markdown([_c("retired")], active_only=True)
    assert "C-001" not in md


def test_denied_rendered_as_false_positive():
    md = render_markdown([_c("denied")])
    assert "false-positive" in md.lower()
    assert "C-001" in md
