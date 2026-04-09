#!/usr/bin/env python3
"""
combo_analyzer.py — Multi-skill combination risk analyzer
Version: 1.0.0

Analyzes risk amplification when multiple skills are loaded simultaneously.
Individual skills may score LOW, but certain combinations create compound risks
that static per-skill scoring cannot detect.

Usage:
    python combo_analyzer.py                          # analyze all installed skills
    python combo_analyzer.py --skills a b c           # analyze specific combo
    python combo_analyzer.py --all ~/.claude/skills   # scan dir + find combos

Combination risk model:
  Certain dimension pairs amplify each other when co-present:
    D1(network) + D5(exfiltration)  → data can leave the system
    D3(execution) + D1(network)     → remote code execution chain
    D3(execution) + D4(filesystem)  → local privilege escalation
    D2(credentials) + D1(network)   → credential theft via network
    D5(exfiltration) + D7(prompt)   → prompt injection → data leak
    D1(network) + D7(prompt)        → prompt injection from remote content

Output: combo risk report + JSONL entry appended to combo_log.jsonl
"""

from __future__ import annotations
import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

SCORER    = Path(__file__).parent / "risk_scorer.py"
SKILLS_DIR = Path("~/.claude/skills").expanduser()
COMBO_LOG  = Path("~/.claude/skills/skill-security-auditor/combo_log.jsonl").expanduser()

# ── Combination amplification rules ──────────────────────────────────────────
# Each rule: (dim_A, dim_A_min_score, dim_B, dim_B_min_score, amplifier, description)
# amplifier: multiplier applied to the lower of the two dim scores → added to combo score
COMBO_RULES = [
    # Network + Exfiltration = data can leave system
    ("D1_network", 2.0, "D5_exfiltration", 2.0, 2.5,
     "Network + Exfiltration: skill can fetch AND send data out"),

    # Execution + Network = remote code execution chain
    ("D3_execution", 2.0, "D1_network", 3.0, 2.0,
     "Execution + Network: arbitrary code execution with network access"),

    # Execution + Filesystem = local privilege escalation
    ("D3_execution", 2.0, "D4_filesystem", 3.0, 1.8,
     "Execution + Filesystem: code execution with broad file access"),

    # Credentials + Network = credential exfiltration
    ("D2_credentials", 2.0, "D1_network", 3.0, 3.0,
     "Credentials + Network: secrets can be sent over the network"),

    # Exfiltration + Prompt Injection = injection → data leak
    ("D5_exfiltration", 2.0, "D7_prompt_inject", 3.0, 2.2,
     "Exfiltration + Prompt Injection: injected content can trigger data leak"),

    # Network + Prompt Injection = remote content injection
    ("D1_network", 3.0, "D7_prompt_inject", 2.0, 1.5,
     "Network + Prompt Injection: fetched content may contain injection"),
]


@dataclass
class SkillDimProfile:
    """Dimension scores for a single skill (from risk_scorer output)."""
    skill_name: str
    final_score: float
    risk_level: str
    dims: dict[str, float]   # dim_name → raw_score (0-10)


@dataclass
class ComboRisk:
    """A triggered combination rule between two skills."""
    skill_a: str
    skill_b: str
    rule_desc: str
    score_a: float   # dim score from skill_a
    score_b: float   # dim score from skill_b
    amplified: float # amplifier × min(score_a, score_b)


@dataclass
class ComboReport:
    scanned_at: str
    skills: list[str]
    individual_scores: dict[str, float]
    combo_risks: list[ComboRisk]
    combo_score: float   # max amplification across all triggered rules
    risk_level: str
    summary: str


# ── Scanning ──────────────────────────────────────────────────────────────────

def _scan_skill(skill_path: Path) -> Optional[SkillDimProfile]:
    """Run risk_scorer --json on a skill and return its dimension profile."""
    result = subprocess.run(
        [sys.executable, str(SCORER), str(skill_path), "--json", "--no-log"],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        data = json.loads(result.stdout)
        if isinstance(data, list):
            data = data[0]
        dims = {}
        for d in data.get("dimensions", []):
            dims[d["name"]] = d["raw_score"]
        return SkillDimProfile(
            skill_name=data["skill_name"],
            final_score=data["final_score"],
            risk_level=data["risk_level"],
            dims=dims,
        )
    except Exception:
        return None


def _scan_all(skills_dir: Path) -> list[SkillDimProfile]:
    """Scan all skills and return their profiles."""
    profiles = []
    skip = {"__pycache__", ".venv", "node_modules"}
    for p in sorted(skills_dir.iterdir()):
        if not p.is_dir() or p.name.startswith(".") or p.name in skip:
            continue
        prof = _scan_skill(p)
        if prof:
            profiles.append(prof)
    return profiles


# ── Combination analysis ──────────────────────────────────────────────────────

def _analyze_pair(a: SkillDimProfile, b: SkillDimProfile) -> list[ComboRisk]:
    """Check all combination rules for a pair of skills."""
    risks = []
    for dim_a, min_a, dim_b, min_b, amp, desc in COMBO_RULES:
        score_a_from_a = a.dims.get(dim_a, 0.0)
        score_b_from_a = a.dims.get(dim_b, 0.0)
        score_a_from_b = b.dims.get(dim_a, 0.0)
        score_b_from_b = b.dims.get(dim_b, 0.0)

        # Case 1: skill_a has dim_A, skill_b has dim_B
        if score_a_from_a >= min_a and score_b_from_b >= min_b:
            amplified = amp * min(score_a_from_a, score_b_from_b)
            risks.append(ComboRisk(
                skill_a=a.skill_name, skill_b=b.skill_name,
                rule_desc=desc,
                score_a=score_a_from_a, score_b=score_b_from_b,
                amplified=round(amplified, 1),
            ))

        # Case 2: skill_b has dim_A, skill_a has dim_B (reverse)
        elif score_a_from_b >= min_a and score_b_from_a >= min_b:
            amplified = amp * min(score_a_from_b, score_b_from_a)
            risks.append(ComboRisk(
                skill_a=b.skill_name, skill_b=a.skill_name,
                rule_desc=desc,
                score_a=score_a_from_b, score_b=score_b_from_a,
                amplified=round(amplified, 1),
            ))

        # Case 3: single skill has BOTH dimensions (self-amplification)
        elif score_a_from_a >= min_a and score_b_from_a >= min_b:
            amplified = amp * min(score_a_from_a, score_b_from_a) * 0.5  # half weight
            risks.append(ComboRisk(
                skill_a=a.skill_name, skill_b=a.skill_name,
                rule_desc=f"[Self] {desc}",
                score_a=score_a_from_a, score_b=score_b_from_a,
                amplified=round(amplified, 1),
            ))

    return risks


def _combo_risk_level(score: float) -> tuple[str, str]:
    if score < 10:  return "LOW",      "No combination risk detected"
    if score < 20:  return "MEDIUM",   "Moderate combination risk — review interaction"
    if score < 35:  return "HIGH",     "High combination risk — restrict co-loading"
    return              "CRITICAL", "Critical combination risk — do not load together"


def analyze_combo(profiles: list[SkillDimProfile]) -> ComboReport:
    """Analyze all pairs in a set of profiles for combination risks."""
    all_risks: list[ComboRisk] = []

    for i, a in enumerate(profiles):
        for b in profiles[i:]:   # includes self (i==j) for self-amplification
            pair_risks = _analyze_pair(a, b)
            all_risks.extend(pair_risks)

    # Deduplicate identical rules
    seen = set()
    deduped = []
    for r in all_risks:
        key = (r.skill_a, r.skill_b, r.rule_desc)
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    combo_score = round(max((r.amplified for r in deduped), default=0.0), 1)
    level, summary = _combo_risk_level(combo_score)

    return ComboReport(
        scanned_at=datetime.now(timezone.utc).isoformat(),
        skills=[p.skill_name for p in profiles],
        individual_scores={p.skill_name: p.final_score for p in profiles},
        combo_risks=sorted(deduped, key=lambda r: -r.amplified),
        combo_score=combo_score,
        risk_level=level,
        summary=summary,
    )


# ── Output ────────────────────────────────────────────────────────────────────

def _report_text(r: ComboReport) -> str:
    lines = [
        f"\n{'='*65}",
        f"  COMBINATION RISK REPORT",
        f"{'='*65}",
        f"  Skills analyzed : {len(r.skills)}",
        f"  Combo score     : {r.combo_score}  [{r.risk_level}]",
        f"  Summary         : {r.summary}",
        f"  Scanned         : {r.scanned_at}",
    ]
    if r.combo_risks:
        lines += ["", f"  Triggered rules ({len(r.combo_risks)}):"]
        for cr in r.combo_risks[:10]:
            same = cr.skill_a == cr.skill_b
            pair = cr.skill_a if same else f"{cr.skill_a} ↔ {cr.skill_b}"
            lines.append(
                f"    [{cr.amplified:>5.1f}] {pair}\n"
                f"           {cr.rule_desc}"
            )
        if len(r.combo_risks) > 10:
            lines.append(f"    ... +{len(r.combo_risks)-10} more rules triggered")
    else:
        lines.append("\n  ✅ No combination risks detected.")
    lines.append("=" * 65)
    return "\n".join(lines)


def _append_log(r: ComboReport) -> None:
    COMBO_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": r.scanned_at,
        "skills": r.skills,
        "combo_score": r.combo_score,
        "risk_level": r.risk_level,
        "top_risks": [asdict(cr) for cr in r.combo_risks[:5]],
    }
    with COMBO_LOG.open("a") as f:
        f.write(json.dumps(entry) + "\n")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-skill combination risk analyzer")
    parser.add_argument("--skills", nargs="+", metavar="SKILL",
                        help="Specific skill names to analyze together")
    parser.add_argument("--all", metavar="SKILLS_DIR",
                        help="Scan all skills in dir and find worst combinations")
    parser.add_argument("--no-log", action="store_true", help="Skip combo log")
    parser.add_argument("--top", type=int, default=10,
                        help="Show top N riskiest pairs (--all mode only)")
    args = parser.parse_args()

    if args.all:
        base = Path(args.all).expanduser()
        print(f"Scanning {base} for combination risks…")
        profiles = _scan_all(base)
        print(f"Loaded {len(profiles)} skill profiles. Analyzing pairs…")

        # Find top riskiest pairs
        pair_reports: list[tuple[float, str, str, list[ComboRisk]]] = []
        for i, a in enumerate(profiles):
            for b in profiles[i+1:]:
                risks = _analyze_pair(a, b)
                if risks:
                    score = max(r.amplified for r in risks)
                    pair_reports.append((score, a.skill_name, b.skill_name, risks))

        pair_reports.sort(key=lambda x: -x[0])

        print(f"\n{'='*65}")
        print(f"  TOP {args.top} RISKIEST SKILL PAIRS")
        print(f"{'='*65}")
        for score, na, nb, risks in pair_reports[:args.top]:
            level, _ = _combo_risk_level(score)
            print(f"  [{score:>5.1f}] [{level:<8}] {na} ↔ {nb}")
            for r in risks[:2]:
                print(f"           ↳ {r.rule_desc}")
        print(f"{'='*65}")
        print(f"\n  Total pairs with combo risk: {len(pair_reports)}")

        if not args.no_log:
            # Log the full set as one report
            report = analyze_combo(profiles)
            _append_log(report)

    elif args.skills:
        profiles = []
        for name in args.skills:
            path = SKILLS_DIR / name
            if not path.exists():
                print(f"Warning: skill '{name}' not found in {SKILLS_DIR}", file=sys.stderr)
                continue
            prof = _scan_skill(path)
            if prof:
                profiles.append(prof)

        if len(profiles) < 1:
            print("No valid skills found.", file=sys.stderr)
            sys.exit(1)

        report = analyze_combo(profiles)
        print(_report_text(report))
        if not args.no_log:
            _append_log(report)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
