# claude-skills

**Language / 语言 / Idioma / Langue / Idioma / 言語**
[English](./README.md) · [中文](./README.zh.md) · [Español](./README.es.md) · [Français](./README.fr.md) · [Português](./README.pt.md) · [日本語](./README.ja.md)

---

> **Canonical source:** This repository — [github.com/WilliamHE-cyber/claude-skills](https://github.com/WilliamHE-cyber/claude-skills) — is the only official version. Forks and mirrors may exist; when in doubt, refer here for the authoritative audit history and approved releases. Copyright © WilliamHE-cyber.

A curated, security-audited collection of Claude Code skills.
Every skill in this repo is scanned weekly by the built-in `skill-security-auditor` before it reaches you.

---

## Skills

| Skill | Version | Risk Score | Description |
|-------|---------|------------|-------------|
| [skill-security-auditor](./skill-security-auditor/) | 0.2.1 | self-exempt | Audits installed Claude skills for security risks across 7 dimensions. Self-iterates on its own detection logic. |

---

## skill-security-auditor

> **An MVP security auditor for Claude Code skills — designed to find its own blind spots and fix them.**

### The Problem

Claude Code skills are Markdown files that instruct Claude to run shell commands, call external APIs, read and write files, and handle credentials. A malicious or poorly written skill could exfiltrate data, execute arbitrary code, or silently leak API keys. There is currently no standard way to assess the risk of a skill before loading it.

### What This Skill Does

`skill-security-auditor` performs static analysis on every skill in your `~/.claude/skills/` directory. It scores each skill across 7 risk dimensions, produces a structured report, maintains an append-only audit log, and — crucially — flags gaps in its own detection logic so it can be improved over time.

---

### 7-Dimension Risk Scoring Matrix

Each dimension is scored **0–10** and combined into a final **0–100** score.

| # | Dimension | Weight | What It Catches |
|---|-----------|--------|-----------------|
| D1 | **Network Exposure** | 20% | External HTTP calls, dynamic URL construction, raw sockets |
| D2 | **Credential Access** | 20% | API keys, tokens, `.env` files, keychain access |
| D3 | **Code Execution** | 18% | `subprocess`, `eval`, `exec`, `sudo`, pipe-to-shell |
| D4 | **File System Access** | 15% | Reads/writes outside workspace, access to `~/.ssh`, `~/.aws` |
| D5 | **Data Exfiltration** | 12% | Conversation data sent externally, base64-encoded payloads |
| D6 | **Dependency Risk** | 8% | `git+` URLs, unpinned versions, non-PyPI indexes |
| D7 | **Prompt Injection Surface** | 7% | Fetched content inserted into prompts without sanitisation |

**Risk levels:**

| Score | Level | Action |
|-------|-------|--------|
| 0–19 | 🟢 LOW | No action required |
| 20–39 | 🟡 MEDIUM | Review within 30 days |
| 40–59 | 🟠 HIGH | Review within 7 days |
| 60–79 | 🔴 CRITICAL | Quarantine pending review |
| 80–100 | ⛔ BLOCKED | Do not load; require human approval |

---

### Three-Layer Check Protocol

The auditor runs three phases on every skill — not just static analysis.

```
┌─────────────────────────────────────────────────────────┐
│  PRE-CHECK          Before loading a skill               │
│  • Parse frontmatter  • Blocklist lookup (30-day window) │
│  • Dependency scan    • Author provenance check          │
├─────────────────────────────────────────────────────────┤
│  RUNTIME CHECK      During skill execution               │
│  • Unexpected tool use    • Credential env var access    │
│  • Undocumented network   • Data egress patterns         │
├─────────────────────────────────────────────────────────┤
│  POST-CHECK         After audit completes                │
│  • Regression detection   • False-positive review        │
│  • Scorer calibration     • Report generation            │
└─────────────────────────────────────────────────────────┘
```

---

### Self-Improvement Loop

This is the core design principle: **the auditor improves itself through use.**

After every scan, `risk_scorer.py` emits `self_notes` — structured observations about its own detection quality:

- Suspected false positives (low score but many hits)
- Inverted or overly broad signal patterns
- Missing signals for known-bad patterns

These notes are written to the audit log (`audit_log.jsonl`) and surfaced in reports. On the next iteration cycle, the scorer reads its own notes and proposes concrete fixes to `SIGNALS` patterns, weights, or scoring logic — then waits for human confirmation before applying changes.

```
scan → self_notes → improvement proposal → human confirms → patch → re-scan → verify
```

**Version history driven by self-discovery:**

| Version | Trigger | Fix |
|---------|---------|-----|
| v0.1.0 | Initial | 7-dimension static scanner |
| v0.2.0 | Self-note: "D1 hits all in code fences" | Excluded ` ``` ` blocks from scanning; fixed D6 `>=` false positive; rebuilt D7 |
| v0.2.1 | Automated prose analysis of `cosmos-policy` | Narrowed D2 `token` pattern — was matching ML vocabulary ("tokenizer", "discrete tokens") |

---

### Usage

Install by placing the skill directory in `~/.claude/skills/`:

```bash
git clone https://github.com/WilliamHE-cyber/claude-skills.git
cp -r claude-skills/skill-security-auditor ~/.claude/skills/
```

Then use it in any Claude Code session:

```
# Scan all installed skills
/security-audit

# Scan one skill
/security-audit langchain

# View audit log summary
/security-audit --log

# Trigger a self-improvement cycle
/security-audit --iterate

# Pre-install check before loading a new skill
/security-audit --pre some-new-skill
```

**Example output:**

```
============================================================
  SKILL RISK REPORT — autogpt
============================================================
  Score : 37.6/100   [MEDIUM]
  Action: Review within 30 days

  Dimension breakdown:
    D1_network             4.0/10  [####      ]  contrib=8.00
      L  44: [HTTP URL literal]  git clone https://github.com/...
    D2_credentials         5.0/10  [#####     ]  contrib=10.00
      L  48: [.env file reference]  cp .env.example .env
    D3_execution           2.0/10  [##        ]  contrib=3.60

  Scorer self-notes (for iteration):
    ⚙ D1: All network hits are URL literals in documentation examples
============================================================
```

---

### Automated Weekly Audits

This repo runs a scheduled Claude Code agent every **Monday at 9:00 AM** that:

1. Clones this repo fresh
2. Runs a full scan with `risk_scorer.py`
3. Detects regressions (score increase > 10 pts since last scan)
4. Generates a report in `skill-security-auditor/reports/`
5. If `self_notes` are non-empty: lists proposed improvements and waits for human approval before changing any code
6. Commits the report back to the repo

Audit reports are public and versioned — you can see the full history in [`skill-security-auditor/reports/`](./skill-security-auditor/reports/).

---

### Architecture

```
skill-security-auditor/
├── SKILL.md                      Entry point — instructions for Claude
├── references/
│   ├── risk_scorer.py            Static scanner (Python, runnable standalone)
│   ├── scoring_matrix.md         7-dimension rubric + calibration history
│   └── audit_log_schema.md       JSONL audit log format + query recipes
└── templates/
    └── audit_report.md           Weekly report template
```

**Audit log** (`audit_log.jsonl`, local) — append-only JSONL, one entry per scan:

```json
{
  "ts": "2026-04-08T16:00:00Z",
  "skill": "langchain",
  "score": 38.4,
  "level": "MEDIUM",
  "scorer_v": "0.2.1",
  "dims": { "D1_network": {"raw": 3.0, "hits": 2}, "..." : "..." },
  "self_notes": [],
  "fp_candidates": []
}
```

---

### Contributing

1. **Adding a skill** — Create `your-skill-name/SKILL.md` with required frontmatter and open a PR. The weekly audit runs automatically; skills scoring CRITICAL or BLOCKED will not be merged.

2. **Improving the scanner** — Found a false positive or a missing signal? Open an issue with the skill name, the flagged line, and why it's wrong. Or run `/security-audit --iterate` locally and attach the proposed diff.

3. **Calibration notes** — If you adjust weights or thresholds, add a `## Calibration Note` entry to `scoring_matrix.md` with the date and rationale.

---

### License

MIT — see [LICENSE](./LICENSE)

*Built with [Claude Code](https://claude.ai/claude-code) · Audited by itself · Self-iterating since v0.1.0*
