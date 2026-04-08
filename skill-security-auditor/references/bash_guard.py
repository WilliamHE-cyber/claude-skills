#!/usr/bin/env python3
"""
bash_guard.py — PreToolUse hook for the Bash tool
Intercepts dangerous shell commands before execution.

This is the Policy Engine's runtime layer:
- Blocks DENY-level patterns immediately (exit 2)
- Warns on LIMIT-level patterns (exit 1)
- Passes everything else through (exit 0)

Does NOT replace the static skill scanner — it's a complementary
runtime check that catches dynamically-constructed dangerous commands.

Version: 0.1.0
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

GATE_LOG = Path("~/.claude/skills/skill-security-auditor/gate_log.jsonl").expanduser()

# ── Policy rules ──────────────────────────────────────────────────────────────
# Each rule: (decision, regex_pattern, description)
# Rules are checked in order; first match wins.

DENY_RULES = [
    # Data exfiltration via pipe to network
    (r"curl.*\|\s*(?:ba)?sh|wget.*\|\s*(?:ba)?sh",
     "Remote code execution via pipe-to-shell"),
    # Recursive deletion of system or home paths
    (r"rm\s+(?:-\S*r\S*|-\S*f\S*\s+-\S*r\S*)\s+(?:/(?!tmp)|~|\.\.)",
     "Recursive deletion of system/home path"),
    # Fork bomb
    (r":\(\s*\)\s*\{.*:\|:.*\}",
     "Fork bomb pattern"),
    # Exfiltrate credentials via network
    (r"(?:curl|wget|nc|ncat).*(?:AWS|SECRET|TOKEN|API_KEY|PRIVATE_KEY)",
     "Credential exfiltration via network tool"),
    # Write to SSH authorized_keys
    (r">>?\s*~?/?\.ssh/authorized_keys",
     "Writing to SSH authorized_keys"),
    # Disable system firewall
    (r"(?:ufw|iptables|pfctl)\s+(?:disable|--flush|-F)",
     "Firewall disable/flush"),
]

LIMIT_RULES = [
    (r"\bsudo\b",
     "sudo usage — elevated privilege"),
    (r"rm\s+.*-[rRf]",
     "Recursive or force delete"),
    (r"chmod\s+(?:777|a\+[rwx])",
     "Overly permissive chmod"),
    (r"(?:curl|wget)\s+.*-[oO]",
     "Downloading file to disk"),
    (r">\s*/etc/",
     "Writing to /etc/"),
    (r"(?:export|set)\s+.*(?:KEY|TOKEN|SECRET|PASSWORD)\s*=",
     "Setting credential environment variable"),
    (r"base64\s+(?:-d|--decode)",
     "Base64 decode (potential payload)"),
    (r"nohup|&\s*$|disown",
     "Background process detachment"),
]


def _log(command: str, decision: str, rule: str):
    GATE_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "hook": "bash_guard",
        "decision": decision,
        "rule": rule,
        "command_preview": command[:120],
    }
    with GATE_LOG.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def main():
    try:
        hook_input = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    if tool_name != "Bash":
        sys.exit(0)

    command = hook_input.get("tool_input", {}).get("command", "")
    if not command:
        sys.exit(0)

    # Check DENY rules
    for pattern, description in DENY_RULES:
        if re.search(pattern, command, re.IGNORECASE):
            _log(command, "DENY", description)
            print(
                f"⛔ BLOCKED by bash_guard (skill-security-auditor)\n"
                f"   Rule   : {description}\n"
                f"   Command: {command[:100]}\n"
                f"   This command matches a DENY policy. Execution refused.\n"
                f"   If this is legitimate, review and adjust the policy rules in bash_guard.py.",
                file=sys.stderr
            )
            sys.exit(2)

    # Check LIMIT rules
    for pattern, description in LIMIT_RULES:
        if re.search(pattern, command, re.IGNORECASE):
            _log(command, "LIMIT", description)
            print(
                f"⚠️  bash_guard WARNING (skill-security-auditor)\n"
                f"   Rule   : {description}\n"
                f"   Command: {command[:100]}\n"
                f"   Proceeding with caution — this pattern requires attention.",
                file=sys.stderr
            )
            sys.exit(1)  # Warn but allow

    sys.exit(0)


if __name__ == "__main__":
    main()
