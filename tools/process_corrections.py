"""Corrections-processing step: ingest inbox -> ledger, render the Corrections
tab, and never silently drop or duplicate a human correction (final-review
finding D). Parsed entries are consumed; unparsed lines are preserved in the
inbox and reported non-zero."""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from tools.ledger import (
    Correction, ingest_inbox, load_ledger, render_markdown, save_ledger,
)

_AUTHOR_RE = re.compile(r"-\s+author:\s*.+$")
_KEY_RE = re.compile(r"\s+(target|correction):\s*.*$")


def find_unparsed(inbox_text: str) -> list[str]:
    """Non-blank inbox lines that ledger.parse_inbox does NOT fold into an
    entry (orphan preamble, or a stray line before the first target/correction
    key). Faithfully mirrors parse_inbox's grammar: while inside a
    target/correction value, ANY non-blank line is a continuation (no indent
    required, and a blank line does not end it). This guarantees a line the
    ledger ingests is never also reported as unparsed (which would rewrite it
    back to the inbox and re-ingest it as a duplicate)."""
    unparsed: list[str] = []
    in_entry = False
    last_key: str | None = None
    for raw in inbox_text.splitlines():
        if _AUTHOR_RE.match(raw):
            in_entry, last_key = True, "author"
            continue
        if not raw.strip():
            continue  # blank line: skip; like parse_inbox, do NOT reset the key
        if not in_entry:
            unparsed.append(raw)  # non-blank preamble before any entry
            continue
        key_match = _KEY_RE.match(raw)
        if key_match:
            last_key = key_match.group(1)
            continue
        if last_key in ("target", "correction"):
            continue  # continuation of the current value (parse_inbox folds it in)
        unparsed.append(raw)  # non-blank while last_key == "author": dropped by parse_inbox
    return unparsed


@dataclass
class ProcessResult:
    new_items: list[Correction]
    ledger: list[Correction]
    corrections_md: str
    unparsed: list[str]


def process(inbox_text: str, ledger_items: list[Correction], today: str) -> ProcessResult:
    unparsed = find_unparsed(inbox_text)
    new_items, _remaining = ingest_inbox(inbox_text, ledger_items, today)
    ledger = ledger_items + new_items
    return ProcessResult(new_items, ledger, render_markdown(ledger), unparsed)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        sys.stderr.write("usage: process_corrections <date> [analysis_dir]\n")
        return 2
    date = argv[0]
    analysis_dir = Path(argv[1] if len(argv) > 1 else os.environ.get("ANALYSIS_DIR", "."))
    corr = analysis_dir / "corrections"
    inbox, ledger_path = corr / "inbox.md", corr / "ledger.jsonl"
    inbox_text = inbox.read_text(encoding="utf-8") if inbox.exists() else ""
    result = process(inbox_text, load_ledger(ledger_path), date)
    save_ledger(ledger_path, result.ledger)
    tab = analysis_dir / date / "corrections_feedback.md"
    tab.parent.mkdir(parents=True, exist_ok=True)
    tab.write_text(result.corrections_md, encoding="utf-8")
    # Rewrite inbox to exactly the unparsed lines: parsed entries consumed,
    # nothing lost, nothing re-ingested next run.
    corr.mkdir(parents=True, exist_ok=True)
    inbox.write_text(("\n".join(result.unparsed) + "\n") if result.unparsed else "", encoding="utf-8")
    if result.unparsed:
        sys.stderr.write("WARNING: unparsed inbox lines preserved (fix & re-run):\n")
        for line in result.unparsed:
            sys.stderr.write(f"  {line}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
