#!/usr/bin/env python3
"""
skill_gate.py — PreToolUse hook for the Skill tool
Intercepts every skill invocation and enforces ALLOW / LIMIT / DENY.

Claude Code hook protocol:
  - Receives JSON on stdin with: hook_event_name, tool_name, tool_input
  - Exit 0  → ALLOW  (proceed normally)
  - Exit 1  → LIMIT  (Claude sees stderr warning, may still proceed)
  - Exit 2  → DENY   (Claude refuses the tool call, shows stderr to user)

Decision table:
  score  0–39   → ALLOW
  score 40–59   → LIMIT  (warn, log, allow with caveat)
  score 60–79   → LIMIT  (strong warn, require explicit confirmation)
  score 80–100  → DENY   (hard block)

Audit log: appended to ~/.claude/skills/skill-security-auditor/gate_log.jsonl
Version: 0.1.0
"""

import json
import os
import sys
import subprocess
from datetime import datetime, timezone
from pathlib import Path

SCORER = Path("~/.claude/skills/skill-security-auditor/references/risk_scorer.py").expanduser()
GATE_LOG = Path("~/.claude/skills/skill-security-auditor/gate_log.jsonl").expanduser()
SKILLS_DIR = Path("~/.claude/skills").expanduser()

# Scores from last audit log — fast-path cache to avoid re-scanning on every call
AUDIT_LOG = Path("~/.claude/skills/skill-security-auditor/audit_log.jsonl").expanduser()


def _cached_score(skill_name: str) -> float | None:
    """Return the most recent audit score for a skill (within 7 days), or None."""
    if not AUDIT_LOG.exists():
        return None
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    best = None
    try:
        for line in AUDIT_LOG.read_text().splitlines():
            e = json.loads(line)
            if e.get("skill") == skill_name:
                ts = datetime.fromisoformat(e["ts"])
                if ts > cutoff:
                    if best is None or ts > datetime.fromisoformat(best["ts"]):
                        best = e
    except Exception:
        return None
    return best["score"] if best else None


def _live_score(skill_path: Path) -> float | None:
    """Run risk_scorer.py and return the score, or None on failure."""
    try:
        result = subprocess.run(
            [sys.executable, str(SCORER), str(skill_path), "--json"],
            capture_output=True, text=True, timeout=15
        )
        data = json.loads(result.stdout)
        return data[0]["final_score"]
    except Exception:
        return None


def _log_gate_decision(skill_name: str, score: float, decision: str, reason: str):
    GATE_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "skill": skill_name,
        "score": score,
        "decision": decision,
        "reason": reason,
    }
    with GATE_LOG.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def main():
    # Parse hook input
    try:
        hook_input = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # Can't parse → allow (fail open for hook errors)

    tool_name = hook_input.get("tool_name", "")
    if tool_name != "Skill":
        sys.exit(0)

    tool_input = hook_input.get("tool_input", {})
    skill_name = tool_input.get("skill", "").strip()
    if not skill_name:
        sys.exit(0)

    # Resolve skill path
    skill_path = SKILLS_DIR / skill_name
    if not skill_path.exists():
        sys.exit(0)  # Unknown skill → allow (scanner can't assess what it can't find)

    # Get score — cached first, live scan as fallback
    score = _cached_score(skill_name)
    source = "cached"
    if score is None:
        score = _live_score(skill_path)
        source = "live"

    if score is None:
        # Scanner failed → warn but allow
        print(f"⚠️  skill-gate: Could not assess '{skill_name}' — proceeding with caution.", file=sys.stderr)
        sys.exit(0)

    # Decision
    if score >= 80:
        decision = "DENY"
        msg = (
            f"⛔ BLOCKED by skill-security-auditor\n"
            f"   Skill : {skill_name}\n"
            f"   Score : {score:.1f}/100  [BLOCKED]\n"
            f"   Reason: Risk score exceeds 80 — loading refused.\n"
            f"   Action: Run `/security-audit {skill_name}` to review details.\n"
            f"           To override: add `<!-- audit:exempt -->` to SKILL.md after manual review."
        )
        _log_gate_decision(skill_name, score, decision, f"score={score:.1f} >= 80 ({source})")
        print(msg, file=sys.stderr)
        sys.exit(2)

    elif score >= 60:
        decision = "LIMIT"
        msg = (
            f"🔴 CRITICAL RISK — skill-security-auditor\n"
            f"   Skill : {skill_name}\n"
            f"   Score : {score:.1f}/100  [CRITICAL]\n"
            f"   This skill has significant security signals. Review before proceeding.\n"
            f"   Run `/security-audit {skill_name}` for full details."
        )
        _log_gate_decision(skill_name, score, decision, f"score={score:.1f} in [60,80) ({source})")
        print(msg, file=sys.stderr)
        sys.exit(1)

    elif score >= 40:
        decision = "LIMIT"
        msg = (
            f"🟠 HIGH RISK — skill-security-auditor\n"
            f"   Skill : {skill_name}  |  Score: {score:.1f}/100  [HIGH]\n"
            f"   Proceeding with warning. Run `/security-audit {skill_name}` to review."
        )
        _log_gate_decision(skill_name, score, decision, f"score={score:.1f} in [40,60) ({source})")
        print(msg, file=sys.stderr)
        sys.exit(1)

    else:
        decision = "ALLOW"
        _log_gate_decision(skill_name, score, decision, f"score={score:.1f} < 40 ({source})")
        sys.exit(0)


if __name__ == "__main__":
    main()
