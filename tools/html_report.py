"""Render a dated audit run's Markdown tabs into one self-contained report.html."""
from __future__ import annotations

import html as _html
import os
import re
import sys
from pathlib import Path

try:
    import markdown as _markdown
except ModuleNotFoundError:  # pragma: no cover
    _markdown = None

_FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_MERMAID_RE = re.compile(
    r'<pre><code class="language-mermaid">(.*?)</code></pre>', re.DOTALL)


def render_tab(md_text: str) -> str:
    """Strip frontmatter + guidance comments, render Markdown to HTML, and turn
    fenced ```mermaid blocks into <pre class="mermaid"> with un-escaped source."""
    if _markdown is None:
        raise RuntimeError(
            "the 'markdown' library is required — pip install markdown "
            "(see requirements.txt)")
    text = _FRONTMATTER_RE.sub("", md_text)
    text = _COMMENT_RE.sub("", text)
    body = _markdown.markdown(text, extensions=["tables", "fenced_code"])

    def _unmermaid(m: "re.Match[str]") -> str:
        return f'<pre class="mermaid">{_html.unescape(m.group(1))}</pre>'

    return _MERMAID_RE.sub(_unmermaid, body)


_PLACEHOLDER = "<p><em>Not generated this run.</em></p>"

_TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{css}</style></head>
<body>
<header><h1>{title}</h1></header>
<div class="layout">
<nav class="sidebar"><ul>
{nav}
</ul></nav>
<main class="content">
{panes}
</main>
</div>
<script>{mermaid_js}</script>
<script>
mermaid.initialize({{ startOnLoad: true }});
document.querySelectorAll('.nav-item').forEach(function (it) {{
  it.addEventListener('click', function () {{
    document.querySelectorAll('.nav-item').forEach(function (n) {{ n.classList.remove('active'); }});
    document.querySelectorAll('.pane').forEach(function (p) {{ p.classList.remove('active'); }});
    it.classList.add('active');
    document.getElementById(it.dataset.tab).classList.add('active');
  }});
}});
</script>
</body></html>
"""


def _load_asset(name: str) -> str:
    return (Path(__file__).parent / "assets" / name).read_text(encoding="utf-8")


def build_report(run_dir: Path, tabs: list[tuple[str, str]]) -> str:
    run_dir = Path(run_dir)
    nav_items: list[str] = []
    panes: list[str] = []
    for i, (fname, title) in enumerate(tabs):
        active = " active" if i == 0 else ""
        tab_id = f"tab-{i}"
        nav_items.append(
            f'<li class="nav-item{active}" data-tab="{tab_id}">{title}</li>')
        md_path = run_dir / fname
        body = render_tab(md_path.read_text(encoding="utf-8")) if md_path.exists() else _PLACEHOLDER
        panes.append(f'<section id="{tab_id}" class="pane{active}">{body}</section>')
    return _TEMPLATE.format(
        title=_html.escape(f"Security Analysis — {run_dir.name}"),
        css=_load_asset("report.css"),
        mermaid_js=_load_asset("mermaid.min.js"),
        nav="\n".join(nav_items),
        panes="\n".join(panes),
    )
