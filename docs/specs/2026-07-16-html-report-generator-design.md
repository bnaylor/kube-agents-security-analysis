# Independent HTML Report Generator — Design

**Date:** 2026-07-16
**Author:** Brian Naylor (with Claude Code)
**Status:** Approved design, pending implementation plan

## 1. Context & Motivation

The audit publishes its 13-tab report as a tabbed Google Doc via `generate.sh`,
which shells out to `onedoc` — a binary only available **inside** the corp
environment. To view or share a report outside that environment (and to make the
repo genuinely self-serve for anyone), we need an **independent** way to render a
dated run's Markdown tabs into a browsable, shareable artifact with no `onedoc`
and no server.

This builds the lightweight in-repo HTML generator parked as a future item in the
framework design (spec §8) and the memory of this initiative.

## 2. Decisions (locked)

- **Markdown → HTML via a library** (not hand-rolled): Python-Markdown with the
  `tables` and `fenced_code` extensions. (The audit `tools/` stay stdlib-only;
  this generator carries the one dependency.)
- **Output: a single self-contained HTML file** per dated run — all 13 tabs
  inline, JS tab-switching, inlined CSS. Opens by double-click; trivial to share.
- **Mermaid: vendored inline.** `mermaid.min.js` is bundled in the repo once and
  inlined into each generated file, so diagrams render fully offline / air-gapped.
- **Notification signal: deferred.** The "report ready / corrections due" reviewer
  ping is a separate concern with its own design; out of scope here.

## 3. Goals / Non-Goals

**Goals**
- One command turns a dated run's tabs into `report.html` that renders anywhere,
  offline, with no `onedoc` and no external network.
- A single source of truth for the tab list so the HTML and Google-Doc paths
  cannot drift.

**Non-Goals**
- The reviewer-notification signal (deferred).
- Wiring HTML generation into the SKILL / `generate.sh` publish flow (easy to add
  later; standalone for now).
- A multi-file static site (rejected — single file is the shareable choice).
- Keeping this tool stdlib-only (the markdown library is an accepted dependency).

## 4. Architecture & Files

- **`tools/tabs.py`** — the **canonical** 13-tab manifest: an ordered list of
  `(filename, title)` pairs (Tab 0 What's Changed … Tab 12 Corrections & Feedback,
  exactly matching today's `generate.sh` order/titles). Exposes the list plus a
  `main()` that prints `filename<TAB>title` lines. **`generate.sh` is refactored**
  to build its `create_tab` loop from `python3 -m tools.tabs` instead of its own
  hardcoded list — one source of truth for both output paths.
- **`tools/html_report.py`** — the generator:
  - `render_tab(md_text: str) -> str` — strip YAML frontmatter and `<!-- -->`
    guidance comments, render body via Python-Markdown, post-process mermaid.
  - `build_report(run_dir: Path, tabs: list[tuple[str, str]]) -> str` — assemble
    the full self-contained HTML (sidebar nav + one pane per tab + inlined CSS +
    inlined mermaid.js + init). Missing tab file → a "not generated this run"
    placeholder pane so the nav stays complete.
  - `main(argv)` — resolve date + analysis dir (`ANALYSIS_DIR` env or arg), write
    `<analysis_dir>/<date>/report.html`. CLI: `python3 -m tools.html_report <date> [analysis_dir]`.
- **`tools/html_report.sh`** — thin wrapper (`cd` repo root, `exec python3 -m tools.html_report`).
- **`tools/assets/mermaid.min.js`** — vendored mermaid (pinned version); inlined into output.
- **`tools/assets/report.css`** — stylesheet; inlined into output.
- **`requirements.txt`** (new) — the runtime dep for this tool: `markdown`. (The
  existing `requirements-dev.txt` keeps `pytest`.)

## 5. Markdown → HTML Rendering

Per tab, in `render_tab`:
1. **Strip frontmatter** — a leading `---\n…\n---` block (the `2026-07-15` baseline
   carries redacted `onedoc_*` frontmatter; generated tabs may too).
2. **Strip guidance comments** — `<!-- … -->` blocks (author instructions in the
   templates; harmless but removed for clean output).
3. **Render** with `markdown.markdown(text, extensions=["tables", "fenced_code"])`.
4. **Mermaid post-process** — Python-Markdown renders a ```` ```mermaid ```` block
   as `<pre><code class="language-mermaid">ESCAPED_DIAGRAM</code></pre>`. Rewrite
   each to `<pre class="mermaid">UNESCAPED_DIAGRAM</pre>` (HTML-unescape `&lt; &gt;
   &amp;`) so mermaid.js renders it. This is the only tab feature needing special
   handling.

## 6. Layout & Self-Containment

A single HTML document:
- **Left sidebar** listing the 13 tab titles (mirrors the Google-Doc tab UX);
  **main pane** shows the active tab. Clicking a sidebar item toggles panes via a
  small inline JS `show/hide`; the first tab ("What's Changed") is active on load.
- **Inlined** CSS (clean, readable: system font stack, constrained content width,
  styled tables and code blocks) and **inlined** `mermaid.min.js` + an init call
  (`mermaid.initialize({startOnLoad:true})`, targeting `.mermaid`).
- A header with the report title and date.
- **Zero network** at view time; the file is fully portable.

## 7. CLI, Integration & Errors

- Standalone: `python3 -m tools.html_report 2026-07-16` → `2026-07-16/report.html`
  (or the `.sh` wrapper). Honors `SRC_DIR`/`ANALYSIS_DIR` like the other tools.
- **Not** wired into the SKILL / `generate.sh` flow now (onedoc runs internally;
  this is the independent path). Adding an HTML step to SKILL Step 3 later is a
  one-liner.
- Errors: missing run directory → non-zero exit with a clear message; `import
  markdown` failure → a clear "pip install markdown (see requirements.txt)"
  message; a missing individual tab file → placeholder pane + a stderr note (not
  fatal).

## 8. Testing (pytest)

- `render_tab`: a GFM table → `<table>`; a fenced code block → `<pre><code>`; a
  ```` ```mermaid ```` block → `<pre class="mermaid">` with **un-escaped** content;
  frontmatter and `<!-- -->` comments stripped.
- `build_report`: output contains all 13 tab titles in the sidebar; `mermaid.min.js`
  is inlined; the first tab is marked active; a missing tab file yields the
  placeholder pane.
- `main` (tmp dir): writes `report.html`; missing run dir → non-zero.
- `tabs.py`: the manifest has 13 `(filename, title)` entries in the expected order.
- **Cross-check test**: the tab list emitted by `python3 -m tools.tabs` matches the
  filenames/titles `generate.sh` publishes (guards against the two paths drifting).

## 9. Open / Future

- **Reviewer-notification signal** (deferred): emit a machine-readable run summary
  (path + finding/correction counts) and/or a top-level `index.html` of runs, then
  wire a Slack/GitHub/email ping. Separate design.
- **SKILL integration**: optionally have SKILL Step 3 also emit `report.html`
  alongside the Google Doc.
- **Mermaid size**: vendored `mermaid.min.js` (~2–3 MB) makes each `report.html`
  large; if committed reports become a repo-size concern, revisit (e.g. keep
  reports uncommitted, or a shared asset for a multi-file variant).
