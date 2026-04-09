#!/usr/bin/env python3
"""
run_benchmark.py — Precision/Recall/F1 benchmark for risk_scorer.py
Version: 1.0.0

Usage:
    python run_benchmark.py [--skills-dir ~/.claude/skills]
    python run_benchmark.py --csv    # emit CSV for spreadsheet analysis

Compares actual scanner output against ground-truth labels in benchmark_labels.json.
Prints per-skill pass/fail and aggregate precision, recall, F1 per level bucket.

Definition:
  A skill is correctly classified when its risk_level matches expected_level.
  A FALSE POSITIVE = scanner says MEDIUM/HIGH/CRITICAL/BLOCKED, truth says LOW.
  A FALSE NEGATIVE = scanner says LOW, truth says MEDIUM or higher.
"""

from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

LABELS_FILE = Path(__file__).parent / "benchmark_labels.json"
SCORER      = Path(__file__).parent.parent / "references" / "risk_scorer.py"
SKILLS_DIR  = Path("~/.claude/skills").expanduser()

LEVEL_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL", "BLOCKED"]


def run_scan(skills_dir: Path) -> dict[str, dict]:
    """Run risk_scorer --all --json --no-log and parse output."""
    result = subprocess.run(
        [sys.executable, str(SCORER), "--all", str(skills_dir), "--json", "--no-log"],
        capture_output=True, text=True, timeout=120
    )
    if result.returncode != 0:
        print("Scanner error:", result.stderr[:500], file=sys.stderr)
        sys.exit(1)
    data = json.loads(result.stdout)
    return {r["skill_name"]: r for r in data}


def load_labels() -> dict[str, dict]:
    with LABELS_FILE.open() as f:
        return json.load(f)["skills"]


def level_index(lvl: str) -> int:
    try:
        return LEVEL_ORDER.index(lvl)
    except ValueError:
        return -1


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark risk_scorer against ground truth")
    parser.add_argument("--skills-dir", default=str(SKILLS_DIR), help="Installed skills directory")
    parser.add_argument("--csv", action="store_true", help="Emit CSV output")
    args = parser.parse_args()

    labels  = load_labels()
    results = run_scan(Path(args.skills_dir).expanduser())

    rows = []
    for skill, label in sorted(labels.items()):
        expected = label["expected_level"]
        if skill not in results:
            rows.append({
                "skill": skill, "expected": expected, "actual": "MISSING",
                "score": None, "match": False, "fp": False, "fn": False,
            })
            continue
        r        = results[skill]
        actual   = r["risk_level"]
        score    = r["final_score"]
        match    = actual == expected
        fp       = level_index(actual) > level_index(expected)   # over-scored
        fn       = level_index(actual) < level_index(expected)   # under-scored
        rows.append({
            "skill": skill, "expected": expected, "actual": actual,
            "score": score, "match": match, "fp": fp, "fn": fn,
        })

    # ── Print report ──────────────────────────────────────────────────────────
    if args.csv:
        print("skill,expected,actual,score,match,fp,fn")
        for r in rows:
            print(f"{r['skill']},{r['expected']},{r['actual']},"
                  f"{r['score']},{r['match']},{r['fp']},{r['fn']}")
        return

    # Human-readable report
    print(f"\n{'='*70}")
    print(f"  BENCHMARK REPORT — risk_scorer {_scorer_version()}")
    print(f"  Skills labelled: {len(rows)}  |  Skills scanned: {len(results)}")
    print(f"{'='*70}")

    fps = [r for r in rows if r["fp"]]
    fns = [r for r in rows if r["fn"]]

    if fps:
        print(f"\n🔴 FALSE POSITIVES ({len(fps)}) — scanner over-scored:")
        for r in fps:
            print(f"    {r['skill']:<35}  expected={r['expected']:<9}  "
                  f"actual={r['actual']:<9}  score={r['score']}")

    if fns:
        print(f"\n🟡 FALSE NEGATIVES ({len(fns)}) — scanner under-scored:")
        for r in fns:
            print(f"    {r['skill']:<35}  expected={r['expected']:<9}  "
                  f"actual={r['actual']:<9}  score={r['score']}")

    correct = sum(1 for r in rows if r["match"])
    total   = len(rows)
    fp_rate = len(fps) / total * 100
    fn_rate = len(fns) / total * 100
    acc     = correct / total * 100

    print(f"\n{'─'*70}")
    print(f"  Total skills   : {total}")
    print(f"  Correct labels : {correct}  ({acc:.1f}%)")
    print(f"  False positives: {len(fps)}  ({fp_rate:.1f}%) — scanner too strict")
    print(f"  False negatives: {len(fns)}  ({fn_rate:.1f}%) — scanner too lenient")
    print(f"{'─'*70}")

    # Precision/Recall for HIGH+ detection (the gate-relevant threshold)
    tp = sum(1 for r in rows if level_index(r["actual"]) >= 2 and level_index(r["expected"]) >= 2)
    fp_gate = sum(1 for r in rows if level_index(r["actual"]) >= 2 and level_index(r["expected"]) < 2)
    fn_gate = sum(1 for r in rows if level_index(r["actual"]) < 2 and level_index(r["expected"]) >= 2)
    precision = tp / (tp + fp_gate) if (tp + fp_gate) > 0 else 1.0
    recall    = tp / (tp + fn_gate) if (tp + fn_gate) > 0 else 1.0
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    print(f"\n  Gate threshold (HIGH+) detection:")
    print(f"    Precision : {precision:.2f}  (of alarms raised, how many are real)")
    print(f"    Recall    : {recall:.2f}  (of real risks, how many are caught)")
    print(f"    F1        : {f1:.2f}")
    print(f"{'='*70}\n")


def _scorer_version() -> str:
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("risk_scorer", str(SCORER))
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.SCORER_VERSION
    except Exception:
        return "unknown"


if __name__ == "__main__":
    main()
