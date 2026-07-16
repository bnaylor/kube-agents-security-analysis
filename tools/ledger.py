"""Corrections & Feedback ledger (cross-run). Canonical store: ledger.jsonl."""
from __future__ import annotations

import json
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
