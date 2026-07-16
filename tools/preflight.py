"""Step-0 pre-flight: assert dated path-hints still resolve before analysis."""
from __future__ import annotations

import os
import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from shutil import which


@dataclass
class Check:
    kind: str            # "file" | "dir" | "absent" | "command"
    target: str          # path relative to base, or a shell command
    reason: str
    optional: bool = False


@dataclass
class CheckResult:
    check: Check
    passed: bool
    skipped: bool
    detail: str


@dataclass
class PreflightResult:
    results: list[CheckResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(r.passed or r.skipped or r.check.optional for r in self.results)

    def report_md(self) -> str:
        lines = ["# Pre-flight drift report", ""]
        for r in self.results:
            mark = "PASS" if r.passed else ("SKIP" if r.skipped else "FAIL")
            lines.append(f"- **{mark}** `{r.check.target}` — {r.check.reason} ({r.detail})")
        return "\n".join(lines) + "\n"


def evaluate_check(check: Check, base: Path) -> CheckResult:
    if check.kind == "command":
        exe = shlex.split(check.target)[0]
        if _which(exe) is None:
            return CheckResult(check, passed=False, skipped=True, detail="tool not present")
        proc = subprocess.run(shlex.split(check.target), capture_output=True, text=True)
        return CheckResult(check, passed=proc.returncode == 0, skipped=False,
                           detail=f"exit {proc.returncode}")
    path = base / check.target
    if check.kind == "file":
        return CheckResult(check, path.is_file(), False, "is_file")
    if check.kind == "dir":
        return CheckResult(check, path.is_dir(), False, "is_dir")
    if check.kind == "absent":
        return CheckResult(check, not path.exists(), False, "absent")
    raise ValueError(f"unknown check kind: {check.kind}")


def _which(exe: str):
    return which(exe)


def run_preflight(base: Path, checks: list[Check]) -> PreflightResult:
    return PreflightResult([evaluate_check(c, base) for c in checks])


# as of 2026-07-16 — verify each run
DEFAULT_CHECKS: list[Check] = [
    Check("file", "agents/platform/config.yaml", "single-agent model intact"),
    Check("dir", "agents/platform", "platform agent present"),
    Check("absent", "agents/operator", "operator agent removed (#256)"),
    Check("absent", "agents/devteam", "devteam agent removed (#256)"),
    Check("file", "agents/platform/scripts/platform_mcp_server.py", "MCP server path alive"),
    Check("command", "kubectl get ns kubeagents-system", "install namespace", optional=True),
]


def main() -> int:
    base = Path(os.environ.get("KUBE_AGENTS_DIR", ".")).resolve()
    result = run_preflight(base, DEFAULT_CHECKS)
    sys.stdout.write(result.report_md())
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
