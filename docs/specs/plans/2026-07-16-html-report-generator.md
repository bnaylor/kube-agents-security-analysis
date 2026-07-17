# HTML Report Generator — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render a dated audit run's 13 Markdown tabs into one self-contained `report.html` that opens and renders anywhere, with no `onedoc` and no network.

**Architecture:** A canonical tab manifest (`tools/tabs.py`) is consumed by both the existing `generate.sh` (Google Doc) and a new `tools/html_report.py` (HTML). The HTML generator renders each tab with Python-Markdown, assembles a single-file document with a left-sidebar tab UI, and inlines the CSS and a vendored `mermaid.min.js`.

**Tech Stack:** Python 3, the `markdown` library (Python-Markdown), vendored mermaid.js, bash wrapper, `pytest`.

## Global Constraints

- **`tools/tabs.py` is the single source of truth for the 13 tabs.** `generate.sh`
  and `tools/html_report` both consume it; never hardcode the tab list elsewhere.
- **This tool depends on `markdown`** (Python-Markdown), declared in a new
  `requirements.txt`. The audit `tools/` stay stdlib-only; only `html_report`
  imports `markdown`. Install with `python3 -m pip install markdown` — if the
  system Python is externally-managed (PEP 668), use `--user`,
  `--break-system-packages`, or a venv. If it genuinely cannot be installed,
  report BLOCKED.
- **Tools run as `python3 -m tools.<name>` from the repo root;** `.sh` wrappers
  `cd` to repo root and `exec`.
- **Output:** one self-contained `<analysis_dir>/<date>/report.html` with inlined
  CSS + `mermaid.min.js`; zero network at view time.
- **Mermaid pinned:** `mermaid@10.9.1` vendored at `tools/assets/mermaid.min.js`.

## File Structure

- `tools/tabs.py` — canonical `(filename, title)` manifest + a `main()` that prints
  `filename<TAB>title` lines. (Create)
- `generate.sh` — replace the 13 hardcoded `create_tab` calls with a loop over
  `python3 -m tools.tabs`. (Modify)
- `tools/assets/mermaid.min.js` — vendored mermaid (pinned). (Create)
- `tools/assets/report.css` — the report stylesheet. (Create)
- `requirements.txt` — declares `markdown`. (Create)
- `tools/html_report.py` — `render_tab`, `build_report`, `main`. (Create)
- `tools/html_report.sh` — wrapper. (Create)
- `tests/test_tabs.py`, `tests/test_html_report.py` — pytest. (Create)

---

### Task 1: Canonical tab manifest (`tools/tabs.py`)

**Files:** Create `tools/tabs.py`, `tests/test_tabs.py`.

**Interfaces:**
- Produces: `TABS: list[tuple[str, str]]` (filename, title) in publish order;
  `main(argv=None) -> int` prints `filename\ttitle` lines.

- [ ] **Step 1: Write the failing tests** — `tests/test_tabs.py`:
```python
from tools.tabs import TABS, main


def test_manifest_has_13_tabs_in_order():
    assert len(TABS) == 13
    assert TABS[0] == ("whats_changed.md", "What's Changed")
    assert TABS[-1] == ("corrections_feedback.md", "Corrections & Feedback")
    names = [f for f, _ in TABS]
    assert len(set(names)) == 13
    assert all(f.endswith(".md") for f in names)


def test_main_prints_tab_lines(capsys):
    assert main([]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 13
    assert lines[0] == "whats_changed.md\tWhat's Changed"
    assert lines[-1] == "corrections_feedback.md\tCorrections & Feedback"
```

- [ ] **Step 2: Run — verify fail**: `python3 -m pytest tests/test_tabs.py -q` → `ModuleNotFoundError`.

- [ ] **Step 3: Implement `tools/tabs.py`**:
```python
"""Canonical 13-tab manifest for the audit report — the single source of truth
consumed by generate.sh (Google Doc) and tools.html_report (HTML)."""
from __future__ import annotations

import sys

# (filename, title) in publish order (Tab 0 first).
TABS: list[tuple[str, str]] = [
    ("whats_changed.md", "What's Changed"),
    ("architectural_summary.md", "Architectural & Security Summary"),
    ("threat_model.md", "Threat Model"),
    ("least_privilege_inventory.md", "Least-Privilege Inventory"),
    ("secrets_token_brokering.md", "Secrets & Token Brokering"),
    ("agentic_prompt_injection.md", "Prompt Injection & Untrusted Input"),
    ("agentic_tools_mcp_trust.md", "Tools, MCP & Inter-Agent Trust"),
    ("agentic_skills_autonomy.md", "Skills & Autonomy"),
    ("admission_webhooks.md", "Admission Control (Webhooks)"),
    ("runtime_hardening_network.md", "Runtime Hardening & Network"),
    ("pipeline_cicd_supply_chain.md", "GitOps & CI/CD Integrity"),
    ("data_audit_detection.md", "Data, Audit & Detection"),
    ("corrections_feedback.md", "Corrections & Feedback"),
]


def main(argv: list[str] | None = None) -> int:
    for filename, title in TABS:
        sys.stdout.write(f"{filename}\t{title}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run — verify pass**: `python3 -m pytest tests/test_tabs.py -q` → all pass.

- [ ] **Step 5: Commit**:
```bash
git add tools/tabs.py tests/test_tabs.py
git commit -m "feat(tools): canonical 13-tab manifest (tabs.py)"
```

---

### Task 2: `generate.sh` consumes the manifest

**Files:** Modify `generate.sh`; Test `tests/test_generate_sh.py`.

**Interfaces:** Consumes `python3 -m tools.tabs` (Task 1).

- [ ] **Step 1: Write the failing test** — `tests/test_generate_sh.py`:
```python
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
```

- [ ] **Step 2: Run — verify fail**: `python3 -m pytest tests/test_generate_sh.py -q`
  Expected: FAIL (there are currently 13 `create_tab "${url}"` lines, and no `tools.tabs`).

- [ ] **Step 3: Edit `generate.sh`** — replace the block of 13 `create_tab "${url}" "${target_dir}/<file>.md" "<Title>"` lines with this loop:
```bash
# Publish the tabs from the canonical manifest (tools/tabs.py) so this list
# and the HTML generator can never drift.
while IFS=$'\t' read -r fname title; do
    create_tab "${url}" "${target_dir}/${fname}" "${title}"
done < <( cd "${base_dir}" && python3 -m tools.tabs )
```
Leave the `create_tab()` function definition and everything else unchanged.

- [ ] **Step 4: Run — verify pass**:
```
python3 -m pytest tests/test_generate_sh.py -q     # passes
bash -n generate.sh                                # syntax OK
( python3 -m tools.tabs | wc -l )                  # prints 13
```

- [ ] **Step 5: Commit**:
```bash
git add generate.sh tests/test_generate_sh.py
git commit -m "refactor(pipeline): generate.sh builds tabs from tools.tabs manifest"
```

---

### Task 3: Assets & dependency

**Files:** Create `tools/assets/mermaid.min.js`, `tools/assets/report.css`, `requirements.txt`; Test `tests/test_assets.py`.

**Interfaces:** Produces the vendored asset files and the `markdown` dependency
declaration consumed by Tasks 4–6.

- [ ] **Step 1: Write the failing test** — `tests/test_assets.py`:
```python
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
```

- [ ] **Step 2: Run — verify fail**: `python3 -m pytest tests/test_assets.py -q` → FAIL (files absent).

- [ ] **Step 3: Vendor mermaid + install the dep**:
```bash
mkdir -p tools/assets
curl -sSL https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js -o tools/assets/mermaid.min.js
# install the runtime dep (add --user / --break-system-packages / venv if PEP 668):
python3 -m pip install markdown || python3 -m pip install --user markdown || python3 -m pip install --break-system-packages markdown
```
If `curl` has no network, report BLOCKED (the user vendors the file from the pinned URL). Verify: `ls -la tools/assets/mermaid.min.js` (should be > 100 KB) and `python3 -c "import markdown"` (no error).

- [ ] **Step 4: Write `requirements.txt`**:
```
markdown>=3.5
```

- [ ] **Step 5: Write `tools/assets/report.css`**:
```css
:root { --fg:#1a1a1a; --muted:#666; --border:#e2e2e2; --accent:#2b6cb0; --bg:#fff; --side:#f6f7f9; }
* { box-sizing: border-box; }
body { margin:0; color:var(--fg); background:var(--bg);
  font: 15px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
header { padding:14px 20px; border-bottom:1px solid var(--border); }
header h1 { margin:0; font-size:18px; }
.layout { display:flex; align-items:stretch; }
.sidebar { width:260px; min-width:260px; background:var(--side); border-right:1px solid var(--border);
  height:calc(100vh - 50px); overflow:auto; }
.sidebar ul { list-style:none; margin:0; padding:8px 0; }
.nav-item { padding:8px 18px; cursor:pointer; font-size:14px; color:var(--fg); }
.nav-item:hover { background:#eceef1; }
.nav-item.active { background:#e6effa; color:var(--accent); font-weight:600;
  border-left:3px solid var(--accent); padding-left:15px; }
.content { flex:1; padding:24px 40px; height:calc(100vh - 50px); overflow:auto; }
.pane { display:none; max-width:900px; }
.pane.active { display:block; }
.pane h1 { font-size:24px; } .pane h2 { font-size:19px; margin-top:1.6em; }
.pane table { border-collapse:collapse; width:100%; margin:1em 0; font-size:14px; }
.pane th, .pane td { border:1px solid var(--border); padding:7px 10px; text-align:left; vertical-align:top; }
.pane th { background:var(--side); }
.pane pre { background:#f6f8fa; border:1px solid var(--border); border-radius:6px; padding:12px; overflow:auto; }
.pane code { background:#f0f1f3; padding:1px 4px; border-radius:4px; font-size:13px; }
.pane pre code { background:none; padding:0; }
.pane pre.mermaid { background:var(--bg); border:none; text-align:center; }
.pane a { color:var(--accent); }
```

- [ ] **Step 6: Run — verify pass**: `python3 -m pytest tests/test_assets.py -q` → all pass.

- [ ] **Step 7: Commit**:
```bash
git add tools/assets/mermaid.min.js tools/assets/report.css requirements.txt tests/test_assets.py
git commit -m "feat(tools): vendor mermaid.min.js + report.css, declare markdown dep"
```

---

### Task 4: `render_tab` (Markdown → HTML)

**Files:** Create `tools/html_report.py`; Test `tests/test_html_report.py`.

**Interfaces:**
- Consumes: `markdown` (Task 3).
- Produces: `render_tab(md_text: str) -> str`.

- [ ] **Step 1: Write the failing tests** — `tests/test_html_report.py`:
```python
from tools.html_report import render_tab


def test_render_table():
    md = "| a | b |\n| :-- | :-- |\n| 1 | 2 |\n"
    assert "<table>" in render_tab(md)


def test_render_fenced_code():
    out = render_tab("```python\nx = 1\n```\n")
    assert "<pre>" in out and "x = 1" in out


def test_render_mermaid_unescaped():
    out = render_tab("```mermaid\ngraph TD\n  A --> B\n```\n")
    assert 'class="mermaid"' in out
    assert "A --> B" in out          # un-escaped for mermaid.js
    assert "--&gt;" not in out


def test_strips_frontmatter_and_comments():
    out = render_tab("---\nonedoc_gdoc_url: REDACTED\n---\n<!-- guidance -->\n# Title\n")
    assert "onedoc_gdoc_url" not in out
    assert "guidance" not in out
    assert "<h1>Title</h1>" in out
```

- [ ] **Step 2: Run — verify fail**: `python3 -m pytest tests/test_html_report.py -q` → `ModuleNotFoundError`.

- [ ] **Step 3: Implement `tools/html_report.py`** (render half):
```python
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
```

- [ ] **Step 4: Run — verify pass**: `python3 -m pytest tests/test_html_report.py -q` → all pass.

- [ ] **Step 5: Commit**:
```bash
git add tools/html_report.py tests/test_html_report.py
git commit -m "feat(tools): html_report.render_tab (markdown + mermaid post-process)"
```

---

### Task 5: `build_report` (assemble the self-contained document)

**Files:** Modify `tools/html_report.py`; Modify `tests/test_html_report.py`.

**Interfaces:**
- Consumes: `render_tab` (Task 4); assets via `_load_asset`.
- Produces: `build_report(run_dir: Path, tabs: list[tuple[str, str]]) -> str`.

- [ ] **Step 1: Add the failing test** — append to `tests/test_html_report.py`:
```python
import tools.html_report as hr


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
```

- [ ] **Step 2: Run — verify fail**: `python3 -m pytest tests/test_html_report.py::test_build_report_structure -q` → `AttributeError: build_report`.

- [ ] **Step 3: Extend `tools/html_report.py`** — add below `render_tab`:
```python
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
            f'<li class="nav-item{active}" data-tab="{tab_id}">{_html.escape(title)}</li>')
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
```
Note: only the literal braces in `_TEMPLATE` (the JS) are doubled `{{ }}`; the
substituted values (`css`, `mermaid_js`, rendered bodies) may contain single
braces freely — `str.format` only interprets the template's own braces.

- [ ] **Step 4: Run — verify pass**: `python3 -m pytest tests/test_html_report.py -q` → all pass.

- [ ] **Step 5: Commit**:
```bash
git add tools/html_report.py tests/test_html_report.py
git commit -m "feat(tools): html_report.build_report (self-contained sidebar document)"
```

---

### Task 6: `main` + wrapper (write `report.html`)

**Files:** Modify `tools/html_report.py`; Create `tools/html_report.sh`; Modify `tests/test_html_report.py`.

**Interfaces:**
- Consumes: `build_report` (Task 5); `tools.tabs.TABS` (Task 1).
- Produces: `main(argv=None) -> int`; CLI `python3 -m tools.html_report <date> [analysis_dir]`.

- [ ] **Step 1: Add the failing tests** — append to `tests/test_html_report.py`:
```python
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
```

- [ ] **Step 2: Run — verify fail**: `python3 -m pytest tests/test_html_report.py::test_main_writes_report -q` → `AttributeError: main`.

- [ ] **Step 3: Extend `tools/html_report.py`** — add at the end:
```python
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
```

- [ ] **Step 4: Run — verify pass**: `python3 -m pytest tests/test_html_report.py -q` → all pass; then full suite `python3 -m pytest -q`.

- [ ] **Step 5: Add the wrapper** — `tools/html_report.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 -m tools.html_report "$@"
```
Then `chmod +x tools/html_report.sh`.

- [ ] **Step 6: Real end-to-end smoke** (against the committed baseline run):
```
python3 -m tools.html_report 2026-07-15 .
```
Expected: `wrote 2026-07-15/report.html`. Open it — 13 tabs in the sidebar, the
Architectural tab's mermaid diagram renders, tables are styled. (This is a manual
visual check; it is not a pytest.)

- [ ] **Step 7: Commit**:
```bash
git add tools/html_report.py tools/html_report.sh tests/test_html_report.py
git commit -m "feat(tools): html_report main + wrapper (write self-contained report.html)"
```

---

## Self-Review

**Spec coverage:**
- `tabs.py` canonical manifest + `generate.sh` refactor (spec §4) → Tasks 1–2. ✓
- Python-Markdown + tables/fenced_code, frontmatter/comment strip, mermaid post-process (spec §5) → Task 4. ✓
- Single self-contained file, sidebar, inlined CSS + mermaid.js, first-tab active, missing-tab placeholder (spec §6) → Tasks 3, 5. ✓
- CLI `python3 -m tools.html_report <date> [analysis_dir]` + wrapper + errors (spec §7) → Task 6. ✓
- Vendored `mermaid@10.9.1`, `requirements.txt` markdown dep (spec §2, §4) → Task 3. ✓
- Tests incl. the drift-guard cross-check (spec §8): `tabs.py` manifest test (Task 1) + `generate.sh`-consumes-manifest test (Task 2) together guarantee one source of truth. ✓
- Deferred: notification signal, SKILL integration (spec §3, §9) — intentionally not tasked.

**Placeholder scan:** every code/step block is complete and runnable; commands
have expected output. No TBDs.

**Type consistency:** `render_tab(str)->str`, `build_report(Path, list[tuple[str,str]])->str`,
`main(argv)->int`, `TABS: list[tuple[str,str]]`, `_load_asset(str)->str` are used
consistently across Tasks 1, 4, 5, 6.
