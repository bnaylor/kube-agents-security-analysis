"""Corrections & Feedback ledger (cross-run). Canonical store: ledger.jsonl."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path

STATUSES = ("open", "confirmed", "denied", "absorbed", "retired")

TRANSITIONS: dict[str, set[str]] = {
    "open": {"confirmed", "denied"},
    "confirmed": {"absorbed"},
    "absorbed": {"retired"},
    "denied": set(),
    "retired": set(),
}


class GuardrailError(Exception):
    """Raised when the LLM tries to `deny` a human correction without proof."""


@dataclass
class Correction:
    id: str
    raised: str
    author: str
    target: str
    correction: str
    status: str
    verification: str = ""
    proof: str = ""
    resolution: str = ""
    history: list[dict] = field(default_factory=list)


def transition(c: Correction, new_status: str, today: str, proof: str = "") -> Correction:
    if new_status not in TRANSITIONS.get(c.status, set()):
        raise ValueError(f"illegal transition {c.status} -> {new_status}")
    if new_status == "denied" and not proof.strip():
        raise GuardrailError(
            "cannot deny a human correction without deterministic proof")
    if new_status == "denied":
        c.proof = proof
    c.status = new_status
    c.history.append({"date": today, "status": new_status})
    return c


def load_ledger(path: Path) -> list[Correction]:
    path = Path(path)
    if not path.exists():
        return []
    items: list[Correction] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            items.append(Correction(**json.loads(line)))
    return items


def save_ledger(path: Path, items: list[Correction]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        "".join(json.dumps(asdict(c), ensure_ascii=False) + "\n" for c in items),
        encoding="utf-8",
    )


_ID_RE = re.compile(r"C-(\d+)")


@dataclass
class InboxEntry:
    author: str
    target: str
    correction: str


def parse_inbox(text: str) -> list[InboxEntry]:
    entries: list[InboxEntry] = []
    cur: dict[str, str] | None = None
    key: str = ""
    for raw in text.splitlines():
        m = re.match(r"-\s+author:\s*(.*)$", raw)
        if m:
            if cur:
                entries.append(_finish_entry(cur))
            cur = {"author": m.group(1).strip(), "target": "", "correction": ""}
            key = "author"
            continue
        if cur is None:
            continue
        m = re.match(r"\s+(target|correction):\s*(.*)$", raw)
        if m:
            key = m.group(1)
            cur[key] = m.group(2).strip()
        elif raw.strip() and key in ("target", "correction"):
            cur[key] = (cur[key] + " " + raw.strip()).strip()
    if cur:
        entries.append(_finish_entry(cur))
    return entries


def _finish_entry(cur: dict[str, str]) -> InboxEntry:
    return InboxEntry(cur["author"], cur["target"], cur["correction"])


def next_id(existing: list[Correction]) -> str:
    nums = [int(m.group(1)) for c in existing if (m := _ID_RE.fullmatch(c.id))]
    return f"C-{(max(nums) + 1) if nums else 1:03d}"


def ingest_inbox(inbox_text: str, existing: list[Correction],
                 today: str) -> tuple[list[Correction], str]:
    new: list[Correction] = []
    pool = list(existing)
    for entry in parse_inbox(inbox_text):
        cid = next_id(pool)
        c = Correction(id=cid, raised=today, author=entry.author,
                       target=entry.target, correction=entry.correction,
                       status="open", history=[{"date": today, "status": "open"}])
        new.append(c)
        pool.append(c)
    return new, ""


def render_markdown(items: list[Correction], active_only: bool = True) -> str:
    active = [c for c in items if c.status in ("open", "confirmed", "absorbed")]
    denied = [c for c in items if c.status == "denied"]
    archived = [c for c in items if c.status == "retired"]

    out = ["# Corrections & Feedback", "", "## Active", ""]
    out.extend(_render_entry(c) for c in active)
    if denied:
        if out[-1] != "":
            out.append("")
        out += ["## Documented false-positives", ""]
        out.extend(_render_entry(c) for c in denied)
    if not active_only and archived:
        if out[-1] != "":
            out.append("")
        out += ["## Retired (archived)", ""]
        out.extend(_render_entry(c) for c in archived)
    return "\n".join(out) + "\n"


def _render_entry(c: Correction) -> str:
    parts = [
        f"### {c.id} — {c.status} (raised {c.raised} by {c.author})",
        f"- **Target:** {c.target}",
        f"- **Correction:** {c.correction}",
    ]
    if c.verification:
        parts.append(f"- **Verification:** {c.verification}")
    if c.proof:
        parts.append(f"- **Proof:** {c.proof}")
    if c.resolution:
        parts.append(f"- **Resolution:** {c.resolution}")
    return "\n".join(parts) + "\n"
