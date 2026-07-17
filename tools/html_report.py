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
    """Strip frontmatter + guidance comments, render Markdown to HTML, and move
    fenced ```mermaid blocks into <pre class="mermaid">.

    The diagram source is kept HTML-ESCAPED (as Markdown emits it): mermaid reads
    the element's .textContent, which the browser decodes back to the literal
    characters (`<br/>`, `-->`, `"`). If we un-escaped it here, tags like <br/>
    in labels would be parsed by the browser as real DOM elements before mermaid
    ran, corrupting the diagram — so we deliberately do NOT unescape."""
    if _markdown is None:
        raise RuntimeError(
            "the 'markdown' library is required — pip install markdown "
            "(see requirements.txt)")
    text = _FRONTMATTER_RE.sub("", md_text)
    text = _COMMENT_RE.sub("", text)
    body = _markdown.markdown(text, extensions=["tables", "fenced_code"])

    def _unmermaid(m: "re.Match[str]") -> str:
        return f'<pre class="mermaid">{m.group(1)}</pre>'

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
// Render mermaid lazily: a diagram in a display:none pane measures as zero-size
// and renders with NaN coordinates (broken), so only run mermaid on a pane once
// it is actually visible.
mermaid.initialize({{ startOnLoad: false }});
function renderMermaid(pane) {{
  if (!pane) return;
  var nodes = pane.querySelectorAll('.mermaid:not([data-processed])');
  if (nodes.length) {{ mermaid.run({{ nodes: Array.prototype.slice.call(nodes) }}); }}
}}
renderMermaid(document.querySelector('.pane.active'));
document.querySelectorAll('.nav-item').forEach(function (it) {{
  it.addEventListener('click', function () {{
    document.querySelectorAll('.nav-item').forEach(function (n) {{ n.classList.remove('active'); }});
    document.querySelectorAll('.pane').forEach(function (p) {{ p.classList.remove('active'); }});
    it.classList.add('active');
    var pane = document.getElementById(it.dataset.tab);
    pane.classList.add('active');
    renderMermaid(pane);
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


def main(argv: list[str] | None = None) -> int:
    from tools.tabs import TABS
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        sys.stderr.write("usage: html_report <date> [analysis_dir]\n")
        return 2
    date = argv[0]
    analysis_dir = Path(argv[1] if len(argv) > 1 else os.environ.get("ANALYSIS_DIR", "."))
    run_dir = analysis_dir / date
    if not run_dir.is_dir():
        sys.stderr.write(f"ERROR: no run directory {run_dir}\n")
        return 1
    out = run_dir / "report.html"
    out.write_text(build_report(run_dir, TABS), encoding="utf-8")
    sys.stdout.write(f"wrote {out}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
