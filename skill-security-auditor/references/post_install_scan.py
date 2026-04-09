#!/usr/bin/env python3
"""
post_install_scan.py — PostToolUse hook for the Skill tool.
Version: 1.0.0

Triggered automatically by Claude Code after every Skill tool invocation.
Reads hook input from stdin (JSON), extracts the skill name that was just
installed, runs risk_scorer.py, and:
  - score <  40 → exit 0  (allow — no action)
  - score 40-59 → exit 0  (warn via stderr, but allow — already loaded)
  - score >= 60 → exit 1  (emit strong warning to stderr; log quarantine notice)

NOTE: PostToolUse exit codes differ from PreToolUse:
  - exit 0 = proceed normally
  - exit 1 = surface a warning message to the user (non-blocking in PostToolUse)
  PostToolUse cannot retroactively block an action, but it CAN alert the user
  and log to quarantine for follow-up.

Hook input format (from Claude Code):
  {
    "tool_name": "Skill",
    "tool_input":  { "skill": "<skill-name>", ... },
    "tool_result": { ... }   # result of the Skill tool call
  }
"""

from __future__ import annotations
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCORER     = Path(__file__).parent / "risk_scorer.py"
SKILLS_DIR = Path("~/.claude/skills").expanduser()
LOG_FILE   = Path("~/.claude/skills/skill-security-auditor/gate_log.jsonl").expanduser()


def _log(entry: dict) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def _scan_skill(skill_name: str) -> tuple[float, str]:
    """Run risk_scorer --json on the skill directory. Returns (score, level)."""
    skill_path = SKILLS_DIR / skill_name
    if not skill_path.exists():
        return 0.0, "UNKNOWN"
    result = subprocess.run(
        [sys.executable, str(SCORER), str(skill_path), "--json", "--no-log"],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0 or not result.stdout.strip():
        return 0.0, "SCAN_ERROR"
    try:
        data = json.loads(result.stdout)
        # --json returns a list when used with --all, scalar dict for single skill
        if isinstance(data, list):
            data = data[0]
        return float(data.get("final_score", 0)), data.get("risk_level", "UNKNOWN")
    except Exception:
        return 0.0, "PARSE_ERROR"


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except Exception:
        sys.exit(0)   # not valid JSON — pass through

    tool_name = hook_input.get("tool_name", "")
    if tool_name != "Skill":
        sys.exit(0)

    skill_name = hook_input.get("tool_input", {}).get("skill", "").strip()
    if not skill_name:
        sys.exit(0)

    score, level = _scan_skill(skill_name)
    ts = datetime.now(timezone.utc).isoformat()

    entry = {
        "ts": ts, "hook": "PostToolUse", "skill": skill_name,
        "score": score, "level": level, "action": ""
    }

    if score >= 60:
        msg = (
            f"\n⚠️  POST-INSTALL SECURITY ALERT — {skill_name}\n"
            f"   Risk score : {score}/100  [{level}]\n"
            f"   This skill was just installed but scored {'CRITICAL' if score < 80 else 'BLOCKED'}.\n"
            f"   Recommended action: review the skill or uninstall it.\n"
            f"   Run: python3 ~/.claude/skills/skill-security-auditor/references/risk_scorer.py "
            f"~/.claude/skills/{skill_name}\n"
        )
        print(msg, file=sys.stderr)
        entry["action"] = "QUARANTINE_NOTICE"
        _log(entry)
        sys.exit(1)   # surfaces warning to user in PostToolUse

    elif score >= 40:
        msg = (
            f"\n🟠 Post-install scan: {skill_name} scored {score}/100 [{level}].\n"
            f"   Review recommended within 7 days.\n"
        )
        print(msg, file=sys.stderr)
        entry["action"] = "WARN"
        _log(entry)
        sys.exit(0)

    else:
        entry["action"] = "ALLOW"
        _log(entry)
        sys.exit(0)


if __name__ == "__main__":
    main()
