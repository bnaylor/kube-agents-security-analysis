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
