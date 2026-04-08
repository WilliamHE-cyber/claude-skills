# Contributing to claude-skills

Thank you for your interest in contributing. This document explains the rules,
process, and expectations for all contributions.

---

## Canonical Repository

The **only official version** of this project is:

```
https://github.com/WilliamHE-cyber/claude-skills
```

Forks and mirrors exist and are welcome, but the authoritative source of truth
for skill ratings, audit history, and approved releases is this repository.
When in doubt, defer to the version here.

---

## Maintainer

**WilliamHE-cyber** is the sole maintainer and has final decision-making
authority on all merges, releases, and governance changes.

- PRs are welcome from anyone
- The maintainer may reject any PR without detailed explanation
- Disagreements with a rejection should be raised as a GitHub Issue, not a new PR

---

## How to Add a Skill

### Requirements before opening a PR

1. **Create the directory structure:**
   ```
   your-skill-name/
   ├── SKILL.md          # Required
   └── references/       # Optional: supporting files
   ```

2. **SKILL.md must include valid frontmatter:**
   ```yaml
   ---
   name: your-skill-name
   description: One clear sentence describing what this skill does
   version: 1.0.0
   author: your-github-username
   license: MIT
   tags: [tag1, tag2]
   ---
   ```

3. **Pass the security scan locally before submitting:**
   ```bash
   python3 skill-security-auditor/references/risk_scorer.py \
       --all your-skill-name/ --json --no-log
   ```
   Skills scoring **CRITICAL (60+) or BLOCKED (80+) will not be merged.**
   Include the scan output in your PR description.

4. **No external data collection.** Skills must not instruct Claude to send
   user data, conversation history, or file contents to third-party services
   without explicit user consent declared in the skill description.

5. **No credential harvesting.** Skills must not read API keys or secrets
   from environment variables and transmit them outside the user's machine.

### PR description template

```markdown
## Skill: your-skill-name

**What it does:** (one paragraph)

**Security scan result:**
Score: XX/100  [LEVEL]
(paste full scanner output here)

**Why this score is acceptable:** (if score > 20, explain each flagged dimension)
```

---

## How to Improve the Scanner

`skill-security-auditor/references/risk_scorer.py` is the heart of this project.
Improvements are especially welcome. To propose a change:

1. **Open an Issue first** describing:
   - The false positive or false negative you found
   - Which skill triggered it
   - The specific line and signal pattern involved
   - Your proposed fix (regex, weight change, new dimension)

2. The maintainer will confirm the direction before you write code.

3. Submit a PR that:
   - Bumps `SCORER_VERSION` (patch for signal fixes, minor for new dimensions)
   - Adds a line to the `# CHANGELOG` at the bottom of `risk_scorer.py`
   - Adds a `## Calibration Note` to `scoring_matrix.md` with date and rationale
   - Re-runs the full scan and includes a before/after score delta table

---

## What Will NOT Be Merged

- Skills that score CRITICAL or BLOCKED with no exemption justification
- Skills that instruct Claude to bypass its own safety guidelines
- Modifications to `risk_scorer.py` that weaken detection without strong justification
- Changes that remove the canonical source declaration from README files
- PRs that alter the LICENSE or copyright notice

---

## Code of Conduct

- Be respectful in Issues and PR comments
- Report security vulnerabilities privately via GitHub's Security Advisory feature
  (not as public Issues)
- Do not submit skills designed to test the limits of what the auditor misses —
  open an Issue instead and help improve the scanner

---

## License

By submitting a PR, you agree that your contribution will be licensed under
the same [MIT License](./LICENSE) as the rest of the project, and that you
have the right to make that contribution.

Copyright of the project as a whole remains with **WilliamHE-cyber**.
