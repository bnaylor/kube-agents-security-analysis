"""Deterministic diff inputs for the 'What's Changed' tab."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def diff_dirs(old: Path, new: Path) -> str:
    proc = subprocess.run(
        ["git", "diff", "--no-index", "--", str(old), str(new)],
        capture_output=True, text=True,
    )
    # git diff --no-index: 0 = identical, 1 = differences, >1 = error
    if proc.returncode > 1:
        raise RuntimeError(proc.stderr.strip() or "git diff failed")
    return proc.stdout


def diff_findings(old: list[dict], new: list[dict]) -> dict:
    old_by = {f["id"]: f for f in old}
    new_by = {f["id"]: f for f in new}
    added = [new_by[i] for i in new_by if i not in old_by]
    removed = [old_by[i] for i in old_by if i not in new_by]
    changed = [new_by[i] for i in new_by if i in old_by and new_by[i] != old_by[i]]
    return {"added": added, "removed": removed, "changed": changed}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        sys.stderr.write("usage: diff_reports <old_dir> <new_dir>\n")
        return 2
    try:
        sys.stdout.write(diff_dirs(Path(argv[0]), Path(argv[1])))
    except RuntimeError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
