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
| [skill-security-auditor](./skill-security-auditor/) | 0.2.3 | self-exempt | Active security gatekeeper for Claude Code skills. Scans, scores, blocks, and self-improves. |

---

## skill-security-auditor

> **From passive auditor to active gatekeeper — intercepts every skill invocation, blocks high-risk commands, and improves its own detection logic over time.**

### The Problem

Claude Code skills are Markdown files that instruct Claude to run shell commands, call external APIs, read and write files, and handle credentials. A malicious or poorly written skill could exfiltrate data, execute arbitrary code, or silently leak API keys. There is currently no standard way to assess the risk of a skill before loading it.

### What This Skill Does

`skill-security-auditor` is a four-layer security system that operates continuously — not just when you ask it to:

| Layer | When | Mechanism | What it does |
|-------|------|-----------|--------------|
| **CI Gate** | PR submitted | GitHub Actions | Blocks skills scoring ≥60 from merging |
| **Pre-invocation** | Every skill call | PreToolUse hook | ALLOW / WARN / BLOCK based on risk score |
| **Post-install** | After install | PostToolUse hook | Alerts if newly installed skill is risky |
| **Weekly rescan** | Every Monday 09:00 | Scheduled agent | Full scan + benchmark + combo analysis |

---

### 7-Dimension Risk Scoring Matrix

Each dimension is scored **0–10** and combined into a final **0–100** score.

| # | Dimension | Weight | What It Catches |
|---|-----------|--------|-----------------|
| D1 | **Network Exposure** | 20% | Active HTTP calls, dynamic URL construction, raw sockets |
| D2 | **Credential Access** | 20% | API keys, tokens, `.env` files, keychain access |
| D3 | **Code Execution** | 18% | `subprocess`, `eval`, `exec`, `sudo`, pipe-to-shell |
| D4 | **File System Access** | 15% | Reads/writes outside workspace, `~/.ssh`, `~/.aws` access |
| D5 | **Data Exfiltration** | 12% | Conversation data sent externally, base64-encoded payloads |
| D6 | **Dependency Risk** | 8% | `git+` URLs, unpinned versions, non-PyPI indexes |
| D7 | **Prompt Injection Surface** | 7% | Fetched content inserted into prompts without sanitisation |

**Risk levels and gate actions:**

| Score | Level | Gate action | Hook action |
|-------|-------|-------------|-------------|
| 0–19 | 🟢 LOW | ✅ CI passes | Allow silently |
| 20–39 | 🟡 MEDIUM | ✅ CI passes | Allow silently |
| 40–59 | 🟠 HIGH | ✅ CI passes | 🟠 Warn user |
| 60–79 | 🔴 CRITICAL | ❌ PR blocked | 🔴 Strong warn |
| 80–100 | ⛔ BLOCKED | ❌ PR blocked | ⛔ Execution refused |

---

### Architecture

```
skill-security-auditor/
├── SKILL.md                         Entry point — Claude instructions
├── references/
│   ├── risk_scorer.py    v0.2.3     Core static scanner (7 dimensions)
│   ├── skill_gate.py     v1.0.0     PreToolUse hook — Skill tool
│   ├── bash_guard.py     v1.0.0     PreToolUse hook — Bash tool
│   ├── post_install_scan.py v1.0.0  PostToolUse hook — post-install alert
│   ├── combo_analyzer.py v1.0.0     Multi-skill combination risk analyzer
│   ├── scoring_matrix.md            7-dimension rubric + calibration history
│   └── audit_log_schema.md          JSONL audit log format
├── tests/
│   ├── benchmark_labels.json        Ground-truth labels for 89 skills
│   └── run_benchmark.py             Precision / Recall / F1 measurement
└── templates/
    └── audit_report.md              Report template
```

**Append-only logs** (local, never pushed):

| File | Contents |
|------|----------|
| `audit_log.jsonl` | One entry per risk_scorer scan |
| `gate_log.jsonl` | One entry per PreToolUse / PostToolUse decision |
| `combo_log.jsonl` | One entry per combination analysis run |

---

### Combination Risk Analysis

Individual scores can miss compound threats. `combo_analyzer.py` models how two skills amplify each other's risk when loaded together:

| Rule | Combination | Threat |
|------|-------------|--------|
| D1 + D5 | Network + Exfiltration | Data can leave the system |
| D3 + D1 | Execution + Network | Remote code execution chain |
| D3 + D4 | Execution + Filesystem | Local privilege escalation |
| D2 + D1 | Credentials + Network | Secret theft via network |
| D5 + D7 | Exfiltration + Prompt Injection | Injected content triggers data leak |
| D1 + D7 | Network + Prompt Injection | Remote content injection |

```bash
# Find riskiest pairs among all installed skills
python3 references/combo_analyzer.py --all ~/.claude/skills --top 10

# Analyze a specific combination
python3 references/combo_analyzer.py --skills langchain 0-autoresearch-skill
```

---

### Self-Improvement Loop

After every scan, `risk_scorer.py` emits `self_notes` — structured observations about its own detection quality. These feed the improvement cycle:

```
scan → self_notes → human reviews → patch → re-scan → benchmark verifies
```

**Version history driven by self-discovery:**

| Version | Trigger | Fix |
|---------|---------|-----|
| v0.1.0 | Initial | 7-dimension static scanner |
| v0.2.0 | Self-note: D1 hits inside code fences | Excluded ` ``` ` blocks; fixed D6 `>=` FP; rebuilt D7 |
| v0.2.1 | Auto prose analysis of `cosmos-policy` | Narrowed D2 — was matching ML vocabulary ("tokenizer") |
| v0.2.3 | P0 benchmark-driven | D1 doc-URL FP fix; self-exempt annotation; benchmark suite |

**Benchmark baseline (v0.2.3, 89 skills):**

| Metric | Value |
|--------|-------|
| Accuracy | 97.8% |
| False positive rate | 0.0% |
| False negative rate | 2.2% |
| Gate F1 (HIGH+) | 1.00 |

---

### Installation

```bash
git clone https://github.com/WilliamHE-cyber/claude-skills.git
cp -r claude-skills/skill-security-auditor ~/.claude/skills/
```

Add hooks to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Skill",
        "hooks": [{ "type": "command", "command": "python3 ~/.claude/skills/skill-security-auditor/references/post_install_scan.py", "timeout": 35 }]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Skill",
        "hooks": [{ "type": "command", "command": "python3 ~/.claude/skills/skill-security-auditor/references/skill_gate.py", "timeout": 30 }]
      },
      {
        "matcher": "Bash",
        "hooks": [{ "type": "command", "command": "python3 ~/.claude/skills/skill-security-auditor/references/bash_guard.py", "timeout": 15 }]
      }
    ]
  }
}
```

---

### Usage

```bash
# Scan a single skill
python3 references/risk_scorer.py ~/.claude/skills/langchain

# Scan all installed skills
python3 references/risk_scorer.py --all ~/.claude/skills

# Run benchmark (precision/recall/F1)
python3 tests/run_benchmark.py

# Find riskiest skill combinations
python3 references/combo_analyzer.py --all ~/.claude/skills --top 10
```

---

### Contributing

1. **Adding a skill** — Create `your-skill-name/SKILL.md` with required frontmatter and open a PR. The CI gate runs automatically; skills scoring CRITICAL or BLOCKED will not be merged.

2. **Improving the scanner** — Found a false positive or a missing signal? Open an issue with the skill name, the flagged line, and why it's wrong. Include `run_benchmark.py` output before and after your proposed fix.

3. **Calibration notes** — If you adjust weights or thresholds, add a `## Calibration Note` entry to `scoring_matrix.md` with the date and rationale.

See [CONTRIBUTING.md](./CONTRIBUTING.md) for full guidelines.

---

### License

MIT — see [LICENSE](./LICENSE)

*Built with [Claude Code](https://claude.ai/claude-code) · Audited by itself · Self-iterating since v0.1.0*
