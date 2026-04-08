# Audit Log Schema

## Storage

**Path:** `~/.claude/skills/skill-security-auditor/audit_log.jsonl`

One JSON object per line (JSONL). Never truncate — append only.
Rotate when file exceeds 50 MB: rename to `audit_log.YYYYMMDD.jsonl`.

---

## Entry Schema

```jsonc
{
  "ts":         "2026-04-08T10:00:00Z",   // ISO-8601 UTC timestamp
  "skill":      "langchain",              // skill directory name
  "path":       "/Users/x/.claude/skills/langchain",
  "score":      42.5,                     // 0–100 final weighted score
  "level":      "HIGH",                   // LOW | MEDIUM | HIGH | CRITICAL | BLOCKED
  "scorer_v":   "0.1.0",                  // risk_scorer.py version
  "dims": {
    "D1_network":       { "raw": 4.0, "hits": 3 },
    "D2_credentials":   { "raw": 0.0, "hits": 0 },
    "D3_execution":     { "raw": 6.0, "hits": 2 },
    "D4_filesystem":    { "raw": 2.0, "hits": 1 },
    "D5_exfiltration":  { "raw": 0.0, "hits": 0 },
    "D6_dependencies":  { "raw": 3.0, "hits": 1 },
    "D7_prompt_inject": { "raw": 3.0, "hits": 1 }
  },
  "self_notes":       ["D7: UNTRUSTED check inverted — refine pattern"],
  "fp_candidates":    ["D1: low score but 3 hits — verify manually"],
  // ── three-layer checks (added by SKILL.md runtime checks) ──
  "pre_check": {
    "passed":   true,
    "warnings": []
  },
  "runtime_check": {
    "passed":   true,
    "anomalies": []
  },
  "post_check": {
    "passed":   true,
    "delta_score": 0,       // score change from last audit of this skill
    "regression": false
  }
}
```

---

## Three-Layer Check Fields

### `pre_check` — before skill is loaded/used
| Field | Type | Description |
|-------|------|-------------|
| `passed` | bool | All pre-checks green |
| `warnings` | string[] | Issues found before execution |

Pre-checks performed:
- SKILL.md frontmatter parseable and has required fields
- No `BLOCKED`-level score from previous audit (within 30 days)
- Dependency versions scannable

### `runtime_check` — during skill execution (populated by hook or manual review)
| Field | Type | Description |
|-------|------|-------------|
| `passed` | bool | No anomalies detected |
| `anomalies` | string[] | Unexpected signals observed at runtime |

Runtime anomalies include:
- Unexpected network call to unknown host
- File write outside workspace
- Sudden credential env var access

### `post_check` — after audit completes
| Field | Type | Description |
|-------|------|-------------|
| `passed` | bool | Post-checks green |
| `delta_score` | float | Score vs previous audit of same skill |
| `regression` | bool | Score increased by >10 points since last audit |

---

## Querying the Log

```bash
# All CRITICAL/BLOCKED skills
grep -E '"level":\s*"(CRITICAL|BLOCKED)"' audit_log.jsonl | jq .skill

# Score trend for a specific skill
grep '"skill": "langchain"' audit_log.jsonl | jq '[.ts, .score]'

# Skills with self-notes (needing scorer improvements)
grep -v '"self_notes": \[\]' audit_log.jsonl | jq '{skill, self_notes}'

# Regressions
grep '"regression": true' audit_log.jsonl | jq '{ts, skill, delta_score}'
```

---

## Retention Policy

| Level | Retention |
|-------|-----------|
| LOW | 90 days |
| MEDIUM | 180 days |
| HIGH / CRITICAL / BLOCKED | Forever (legal hold) |

Self-notes and fp_candidates entries feed back into scorer calibration.
Review them monthly and update `scoring_matrix.md` accordingly.
