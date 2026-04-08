#!/usr/bin/env python3
"""
risk_scorer.py — Static risk scanner for Claude skills
Version: 0.2.0  (self-iterating; see CHANGELOG at bottom)

Usage:
    python risk_scorer.py <skill_dir_or_skill_md>
    python risk_scorer.py --all ~/.claude/skills/
    python risk_scorer.py --json <path>   # emit JSON for programmatic use

Output: structured risk report + JSONL audit log entry appended to
        ~/.claude/skills/skill-security-auditor/audit_log.jsonl
"""

from __future__ import annotations
import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Version metadata (bump on every self-improvement iteration) ───────────────
SCORER_VERSION = "0.2.1"
MATRIX_VERSION = "0.1.1"

# ── Audit log path ────────────────────────────────────────────────────────────
AUDIT_LOG = Path("~/.claude/skills/skill-security-auditor/audit_log.jsonl").expanduser()

# ── Scoring weights (must sum to 1.0) ────────────────────────────────────────
WEIGHTS = {
    "D1_network":        0.20,
    "D2_credentials":    0.20,
    "D3_execution":      0.18,
    "D4_filesystem":     0.15,
    "D5_exfiltration":   0.12,
    "D6_dependencies":   0.08,
    "D7_prompt_inject":  0.07,
}

# ── Signal patterns per dimension ─────────────────────────────────────────────
SIGNALS: dict[str, list[tuple[int, str, str]]] = {
    # (score_contribution, regex_pattern, description)
    "D1_network": [
        (2,  r"https?://[a-zA-Z0-9]",              "HTTP URL literal"),
        (3,  r"requests\.",                         "requests library"),
        (3,  r"urllib",                             "urllib usage"),
        (3,  r"WebFetch\s*\(",                      "WebFetch tool call"),
        (4,  r"f['\"]https?://.*\{",               "Dynamic URL construction"),
        (5,  r"socket\.",                           "Raw socket usage"),
        (2,  r"\bcurl\b|\bwget\b",                 "curl/wget in shell"),
    ],
    "D2_credentials": [
        (3,  r"os\.environ",                        "os.environ access"),
        (3,  r"os\.getenv",                         "os.getenv access"),
        # v0.2.1 fix: exclude ML vocabulary — "tokenizer", "token generation", "attention"
        # trigger pattern now requires credential context: _KEY / _TOKEN / _SECRET suffix,
        # or standalone api_key/password/private_key (not substrings of ML terms)
        (5,  r"(?i)\b(api_key|api[-_]secret|access[-_]token|auth[-_]token|password|private_key|secret[-_]key)\b", "Credential keyword"),
        (4,  r"\.env\b",                            ".env file reference"),
        (5,  r"keychain|Keychain",                  "Keychain access"),
        (6,  r"(?i)bearer\s+['\"]",                "Hardcoded bearer token"),
    ],
    "D3_execution": [
        (3,  r"subprocess\.",                       "subprocess usage"),
        (3,  r"os\.system\s*\(",                   "os.system call"),
        (5,  r"\beval\s*\(",                        "eval() call"),
        (5,  r"\bexec\s*\(",                        "exec() call"),
        (4,  r"shell\s*=\s*True",                  "shell=True in subprocess"),
        (6,  r"sudo\b",                             "sudo usage"),
        (7,  r"curl.*\|\s*(?:ba)?sh|wget.*\|\s*(?:ba)?sh", "Pipe to shell"),
        (3,  r"Bash\s*\(",                          "Bash tool call"),
    ],
    "D4_filesystem": [
        (2,  r"(?:Read|Write|open)\s*\(",           "File I/O call"),
        (5,  r"~/\.ssh",                            "SSH dir access"),
        (5,  r"~/\.aws",                            "AWS credentials dir"),
        (5,  r"~/\.claude",                         "Claude config dir"),
        (4,  r"/etc/",                              "/etc access"),
        (3,  r"shutil\.",                           "shutil usage"),
        (4,  r"os\.remove|os\.unlink",              "File deletion"),
        (5,  r"shutil\.rmtree|rm\s+-rf",            "Recursive deletion"),
    ],
    "D5_exfiltration": [
        (4,  r"base64\.",                           "base64 encoding"),
        (5,  r"conversation|user_message|chat_history", "Conversation data ref"),
        (4,  r"zipfile\.|tarfile\.",                "Archive creation"),
        (6,  r"POST.*\{.*content|data.*requests",  "POST with content"),
        (3,  r"json\.dumps.*open|open.*json\.dumps", "JSON dump to file + network"),
    ],
    "D6_dependencies": [
        (3,  r"git\+https?://",                    "git+ dependency URL"),
        (3,  r"pip install\s+(?!-)[^=><\s]+\s*$", "Unpinned pip install"),
        # Narrowed: require package-name context before >= to avoid catching `if x >= 0`
        (2,  r"[\w][\w.\-]+\s*>=\s*\d|==\s*\*",   "Unpinned version spec"),
        (4,  r"--index-url\s+(?!https://pypi\.org)", "Non-PyPI index"),
        (4,  r"--extra-index-url",                 "Extra index URL (supply chain)"),
    ],
    "D7_prompt_inject": [
        (3,  r"WebFetch\s*\(",                      "Fetches remote content (WebFetch)"),
        (4,  r"Read\s*\(.*user|user.*Read\s*\(",   "Reads user-provided paths"),
        (5,  r"f['\"].*\{.*content\}|format.*content", "Template with fetched content"),
        (6,  r"system_prompt.*fetch|fetch.*system_prompt", "Fetched content in system prompt"),
        # UNTRUSTED signal removed — absence-detection now handled in _d7_untrusted_check()
    ],
}


@dataclass
class DimensionResult:
    name: str
    raw_score: float        # 0-10
    weight: float
    weighted: float
    hits: list[dict]        # {line, pattern_desc, snippet}
    capped: bool = False


@dataclass
class SkillRiskReport:
    skill_name: str
    skill_path: str
    scanned_at: str
    scorer_version: str
    matrix_version: str
    dimensions: list[DimensionResult]
    final_score: float      # 0-100
    risk_level: str
    action: str
    false_positive_candidates: list[str] = field(default_factory=list)
    self_notes: list[str] = field(default_factory=list)   # scorer's own observations


# ── Core scanning logic ────────────────────────────────────────────────────────

def _collect_text(skill_path: Path) -> tuple[str, list[tuple[int, str]]]:
    """Return (full_text, [(lineno, line), ...]) for all .md and .py files.

    v0.2.0 fix: For .md files, lines inside ``` code fences are EXCLUDED.
    These are documentation examples, not executable instructions given to Claude.
    .py reference files are scanned in full — they are real code.
    """
    lines_with_no: list[tuple[int, str]] = []
    all_files = list(skill_path.rglob("*.md")) + list(skill_path.rglob("*.py"))
    if skill_path.is_file():
        all_files = [skill_path]
    for fp in all_files:
        try:
            raw_lines = fp.read_text(errors="replace").splitlines()
            is_md = fp.suffix.lower() == ".md"
            in_fence = False
            for i, line in enumerate(raw_lines, 1):
                if is_md:
                    # ``` or ```python etc. toggles fence state
                    if re.match(r"^\s*```", line):
                        in_fence = not in_fence
                        continue        # skip the fence marker line itself
                    if in_fence:
                        continue        # skip code example content
                lines_with_no.append((i, line))
        except Exception:
            pass
    return "\n".join(l for _, l in lines_with_no), lines_with_no


def _d7_untrusted_check(skill_path: Path, d7_hits: list[dict]) -> tuple[float, str | None]:
    """
    v0.2.0 fix: D7 UNTRUSTED absence check (correct direction).
    If the skill fetches remote content (WebFetch hits) but NEVER wraps it in
    an UNTRUSTED marker, that is the real injection risk.
    Returns (extra_score, note).
    """
    if not d7_hits:
        return 0.0, None
    has_webfetch = any("WebFetch" in h["signal"] for h in d7_hits)
    if not has_webfetch:
        return 0.0, None
    # Scan full text (including code blocks) for UNTRUSTED marker
    try:
        full = skill_path.read_text(errors="replace") if skill_path.is_file() \
               else "\n".join(p.read_text(errors="replace")
                              for p in skill_path.rglob("*.md"))
    except Exception:
        return 0.0, None
    if re.search(r"UNTRUSTED|<untrusted>", full, re.IGNORECASE):
        return 0.0, None   # wrapper present — no extra risk
    return 3.0, "D7: WebFetch used but no UNTRUSTED content wrapper found — injection risk elevated"


def _score_dimension(dim: str, lines: list[tuple[int, str]]) -> DimensionResult:
    weight = WEIGHTS[dim]
    hits: list[dict] = []
    accumulated = 0.0

    for lineno, line in lines:
        for score_contrib, pattern, desc in SIGNALS[dim]:
            if re.search(pattern, line, re.IGNORECASE):
                snippet = line.strip()[:80]
                hits.append({"line": lineno, "signal": desc, "snippet": snippet})
                accumulated += score_contrib
                break  # one hit per line per dimension

    raw = min(10.0, accumulated)
    capped = accumulated > 10.0
    return DimensionResult(
        name=dim,
        raw_score=raw,
        weight=weight,
        weighted=round(raw * weight * 10, 2),   # ×10 to get 0-100 contribution
        hits=hits,
        capped=capped,
    )


def _risk_level(score: float) -> tuple[str, str]:
    if score < 20:   return "LOW",      "No action required"
    if score < 40:   return "MEDIUM",   "Review within 30 days"
    if score < 60:   return "HIGH",     "Review within 7 days; add usage warnings"
    if score < 80:   return "CRITICAL", "Quarantine pending review"
    return              "BLOCKED",  "Do not load; require human approval"


def _self_notes(dims: list[DimensionResult], full_text: str) -> list[str]:
    """
    Scorer's own heuristic observations — the seed of self-improvement.
    These get written to audit log so Claude can review and update signals.
    """
    notes = []
    d7 = next((d for d in dims if d.name == "D7_prompt_inject"), None)
    if d7 and any("Missing UNTRUSTED" in h["signal"] for h in d7.hits):
        notes.append(
            "D7: UNTRUSTED wrapper check is inverted — presence of keyword lowers concern, "
            "but scorer currently flags any mention. Refine pattern to detect absence."
        )
    net = next((d for d in dims if d.name == "D1_network"), None)
    if net and net.raw_score >= 2:
        if not any(re.search(r"WebSearch|WebFetch", h["snippet"]) for h in net.hits):
            notes.append(
                "D1: All network hits are URL literals in documentation examples — "
                "may be false positives. Consider skipping lines inside ``` code blocks."
            )
    if not any(d.hits for d in dims):
        notes.append(
            "No signals detected. Skill may be pure-text documentation. "
            "Consider adding a whitelist check to fast-path such skills."
        )
    return notes


def score_skill(skill_path: Path) -> SkillRiskReport:
    name = skill_path.stem if skill_path.is_file() else skill_path.name
    _, lines = _collect_text(skill_path)

    dims = [_score_dimension(dim, lines) for dim in WEIGHTS]

    # v0.2.0: D7 absence-of-UNTRUSTED check (correct direction)
    d7 = next(d for d in dims if d.name == "D7_prompt_inject")
    extra_d7, d7_note = _d7_untrusted_check(skill_path, d7.hits)
    if extra_d7:
        d7.raw_score = min(10.0, d7.raw_score + extra_d7)
        d7.weighted  = round(d7.raw_score * d7.weight * 10, 2)
        d7.hits.append({"line": 0, "signal": "Absent UNTRUSTED wrapper", "snippet": "(full-file check)"})

    final = round(sum(d.weighted for d in dims), 1)
    level, action = _risk_level(final)

    fp_candidates = []
    for d in dims:
        if d.hits and d.raw_score <= 2:
            fp_candidates.append(
                f"{d.name}: low score ({d.raw_score}) but {len(d.hits)} hits — verify manually"
            )

    return SkillRiskReport(
        skill_name=name,
        skill_path=str(skill_path),
        scanned_at=datetime.now(timezone.utc).isoformat(),
        scorer_version=SCORER_VERSION,
        matrix_version=MATRIX_VERSION,
        dimensions=dims,
        final_score=final,
        risk_level=level,
        action=action,
        false_positive_candidates=fp_candidates,
        self_notes=_self_notes(dims, ""),
    )


# ── Output ─────────────────────────────────────────────────────────────────────

def _report_text(r: SkillRiskReport) -> str:
    lines = [
        f"{'='*60}",
        f"  SKILL RISK REPORT — {r.skill_name}",
        f"{'='*60}",
        f"  Score : {r.final_score}/100   [{r.risk_level}]",
        f"  Action: {r.action}",
        f"  Scanned: {r.scanned_at}",
        "",
        "  Dimension breakdown:",
    ]
    for d in r.dimensions:
        bar = "#" * int(d.raw_score)
        lines.append(f"    {d.name:<22} {d.raw_score:>4.1f}/10  [{bar:<10}]  contrib={d.weighted}")
        for h in d.hits[:3]:
            lines.append(f"      L{h['line']:>4}: [{h['signal']}]  {h['snippet']}")
        if len(d.hits) > 3:
            lines.append(f"      ... +{len(d.hits)-3} more hits")
    if r.false_positive_candidates:
        lines += ["", "  False-positive candidates:"]
        for fp in r.false_positive_candidates:
            lines.append(f"    • {fp}")
    if r.self_notes:
        lines += ["", "  Scorer self-notes (for iteration):"]
        for n in r.self_notes:
            lines.append(f"    ⚙ {n}")
    lines.append("=" * 60)
    return "\n".join(lines)


def _append_audit_log(r: SkillRiskReport) -> None:
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": r.scanned_at,
        "skill": r.skill_name,
        "path": r.skill_path,
        "score": r.final_score,
        "level": r.risk_level,
        "scorer_v": r.scorer_version,
        "dims": {d.name: {"raw": d.raw_score, "hits": len(d.hits)} for d in r.dimensions},
        "self_notes": r.self_notes,
        "fp_candidates": r.false_positive_candidates,
    }
    with AUDIT_LOG.open("a") as f:
        f.write(json.dumps(entry) + "\n")


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Skill static risk scorer")
    parser.add_argument("target", nargs="?", help="Skill dir or SKILL.md path")
    parser.add_argument("--all", metavar="SKILLS_DIR", help="Scan all skills in directory")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    parser.add_argument("--no-log", action="store_true", help="Skip audit log append")
    args = parser.parse_args()

    targets: list[Path] = []
    if args.all:
        base = Path(args.all).expanduser()
        targets = [p for p in sorted(base.iterdir()) if p.is_dir()]
    elif args.target:
        targets = [Path(args.target).expanduser()]
    else:
        parser.print_help()
        sys.exit(1)

    reports = []
    for t in targets:
        r = score_skill(t)
        reports.append(r)
        if not args.json:
            print(_report_text(r))
        if not args.no_log:
            _append_audit_log(r)

    if args.json:
        out = []
        for r in reports:
            d = asdict(r)
            out.append(d)
        print(json.dumps(out, indent=2))

    # Summary table for --all
    if args.all and not args.json:
        print("\nSUMMARY")
        print(f"{'Skill':<35} {'Score':>6}  Level")
        print("-" * 55)
        for r in sorted(reports, key=lambda x: -x.final_score):
            print(f"  {r.skill_name:<33} {r.final_score:>5.1f}  {r.risk_level}")


if __name__ == "__main__":
    main()


# ── CHANGELOG (self-iteration history) ────────────────────────────────────────
# v0.1.0  2026-04-08  Initial version. 7 dimensions, static regex scan.
#                     Known gaps: no code-block exclusion, D7 UNTRUSTED check inverted.
#                     Self-note: D1 URL hits in docs = FP; D7 UNTRUSTED presence/absence inverted.
#
# v0.2.1  2026-04-08  Self-improvement cycle #2 (triggered by cosmos-policy deep analysis).
#                     [FIX] D2 credential pattern: narrowed from generic `token` to
#                           credential-specific patterns (api_key, access_token, etc.)
#                           Eliminates FP on ML vocabulary: "tokenizer", "token generation",
#                           "discrete tokens", "attention". Discovered via automated
#                           prose-vs-code-block line analysis of cosmos-policy SKILL.md.
#
# v0.2.0  2026-04-08  Self-improvement cycle #1 (triggered by full-scan self-notes).
#                     [FIX] _collect_text: exclude lines inside ``` fences in .md files.
#                           Eliminates most D1/D2/D3/D4 documentation false positives.
#                     [FIX] D7 UNTRUSTED: removed inverted presence-signal; replaced with
#                           _d7_untrusted_check() — adds risk when WebFetch exists but no
#                           UNTRUSTED wrapper found anywhere in the skill.
#                     [FIX] D6 `>=` pattern narrowed: now requires package-name prefix
#                           ([\w][\w.\-]+\s*>=\d) to avoid matching `if x >= 0`.
#                     Next: D5 `conversation` keyword too broad; D1 WebFetch read vs. write
#                           distinction; exemption syntax; OSV.dev CVE lookup.
