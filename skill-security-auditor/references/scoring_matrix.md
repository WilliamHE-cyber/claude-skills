# Risk Scoring Matrix — 7 Dimensions

## Overview

Each dimension is scored **0–10** (0 = no risk, 10 = critical risk).
Final score = weighted sum, normalised to 0–100.

| # | Dimension | Weight | Rationale |
|---|-----------|--------|-----------|
| D1 | Network Exposure | 0.20 | Exfiltration path; remote C2 risk |
| D2 | Credential Access | 0.20 | Direct secret leak vector |
| D3 | Code / Command Execution | 0.18 | Arbitrary execution = full system compromise |
| D4 | File System Access | 0.15 | Config/key read, data destruction |
| D5 | Data Exfiltration | 0.12 | PII, conversation data sent out |
| D6 | Dependency Risk | 0.08 | Supply-chain compromise |
| D7 | Prompt Injection Surface | 0.07 | Skill hijacking via adversarial inputs |

---

## D1 — Network Exposure

| Score | Indicator |
|-------|-----------|
| 0 | No network calls anywhere in skill |
| 2 | Read-only calls to well-known public APIs (GitHub, npm, PyPI) |
| 4 | Writes to external service (e.g. webhook, logging endpoint) |
| 6 | Dynamic URL construction from user-supplied input |
| 8 | Proxying/relaying data to arbitrary third-party URLs |
| 10 | Raw socket / low-level networking without validation |

**Signals (regex):** `http[s]?://`, `requests\.`, `fetch(`, `urllib`, `WebFetch`, `curl`, `wget`, dynamic f-string URLs

---

## D2 — Credential Access

| Score | Indicator |
|-------|-----------|
| 0 | No references to secrets or env vars |
| 2 | Reads public env vars (e.g. `$HOME`, `$PATH`) |
| 4 | Reads `*_KEY`, `*_TOKEN`, `*_SECRET` env vars |
| 6 | Passes credentials to external call |
| 8 | Stores credentials to disk / logs them |
| 10 | Exfiltrates credentials off-machine |

**Signals:** `os.environ`, `getenv`, `API_KEY`, `SECRET`, `TOKEN`, `PASSWORD`, `PRIVATE_KEY`, `.env`, keychain access

---

## D3 — Code / Command Execution

| Score | Indicator |
|-------|-----------|
| 0 | No shell/eval calls |
| 2 | Runs read-only commands (`ls`, `cat`, `git log`) |
| 4 | Runs commands with user-controlled arguments |
| 6 | Uses `subprocess`, `os.system`, `eval`, `exec` |
| 8 | Runs commands as elevated user or with `sudo` |
| 10 | Downloads and executes remote code |

**Signals:** `Bash(`, `subprocess`, `os.system`, `eval(`, `exec(`, `shell=True`, `sudo`, `chmod`, `curl | sh`, `wget | bash`

---

## D4 — File System Access

| Score | Indicator |
|-------|-----------|
| 0 | No file I/O |
| 2 | Reads files within project workspace only |
| 4 | Reads files outside workspace (home dir, `/etc`) |
| 6 | Writes files outside workspace |
| 8 | Accesses `~/.ssh`, `~/.aws`, `~/.claude`, credentials dirs |
| 10 | Deletes or overwrites system files |

**Signals:** `Read(`, `Write(`, `open(`, `~/.ssh`, `~/.aws`, `/etc/`, `os.path`, `shutil`, `glob`, `find /`

---

## D5 — Data Exfiltration

| Score | Indicator |
|-------|-----------|
| 0 | No user data transmitted externally |
| 2 | Only metadata (version numbers, timing) |
| 4 | Transmits filenames / paths |
| 6 | Transmits file contents or command outputs |
| 8 | Transmits conversation history or user messages |
| 10 | Bulk data exfiltration with obfuscation |

**Signals:** user message passed to external URL, base64-encoded payload, large POST bodies with dynamic content, zipping of workspace

---

## D6 — Dependency Risk

| Score | Indicator |
|-------|-----------|
| 0 | No external dependencies declared |
| 1 | Only pinned, well-audited packages (numpy, requests) |
| 3 | Unpinned versions (`>=`, `*`, latest) |
| 5 | Dependencies with known CVEs (checked at scan time) |
| 7 | `git+` or URL-based dependencies (not from PyPI/npm) |
| 10 | Dependencies from private/anonymous registries |

**Signals:** frontmatter `dependencies:` field, `pip install`, `npm install`, `git+http`, unpinned versions

---

## D7 — Prompt Injection Surface

| Score | Indicator |
|-------|-----------|
| 0 | Skill never processes external text as instructions |
| 2 | Processes static, author-controlled text only |
| 4 | Summarises/translates user-provided content |
| 6 | Fetches and interprets remote content (web pages, files) |
| 8 | Passes fetched content directly into system prompt or tool calls |
| 10 | No sanitisation; fetched content can override skill instructions |

**Signals:** `WebFetch` + LLM call, `Read(user_path)` → prompt, template interpolation with untrusted strings, missing `<UNTRUSTED>` wrapping

---

## Risk Levels

| Final Score | Level | Action |
|-------------|-------|--------|
| 0–19 | LOW | No action required |
| 20–39 | MEDIUM | Review within 30 days |
| 40–59 | HIGH | Review within 7 days; add usage warnings |
| 60–79 | CRITICAL | Quarantine pending review |
| 80–100 | BLOCKED | Do not load; require human approval |

---

## Self-Improvement Protocol

After each audit batch, the scorer should:
1. Check for false positives (flagged indicators with no actual risk path)
2. Check for false negatives (known-bad skills that scored too low)
3. Append a `## Calibration Note` to this file with the date and adjustment rationale
4. Bump the version in `risk_scorer.py` metadata

## Calibration Note — 2026-04-08 (v0.1.1)

**Trigger:** Full scan of 93 skills revealed systematic over-flagging.
BLOCKED count: 10 → 3. CRITICAL: 21 → 3. Skills moved to better-fit levels.

**Changes made in risk_scorer.py v0.2.0:**
- `_collect_text`: now excludes lines inside ``` fences in .md files.
  Most D1/D2/D3/D4 hits were documentation examples, not real instructions.
- D6 `>=` pattern narrowed to require package-name prefix; was catching `if x >= 0`.
- D7 UNTRUSTED signal removed (was inverted); replaced with absence-detection function.

**Representative score deltas:**
| Skill | v0.1 | v0.2 | Assessment |
|-------|------|------|-----------|
| audiocraft | 78.6 CRITICAL | 21.6 MEDIUM | FP fixed: all hits were in code examples |
| lambda-labs | 81.0 BLOCKED | 31.6 MEDIUM | FP fixed: cloud setup docs, not live calls |
| autogpt | 80.6 BLOCKED | 37.6 MEDIUM | Partial FP: real credentials refs remain |
| unsloth | 100.0 BLOCKED | 100.0 BLOCKED | Unchanged: frontmatter + prose refs real |

**Still unclear (needs human review):**
- `skill-security-auditor` scores 96.8 on itself: its own `risk_scorer.py`
  contains real signals (subprocess, eval, os.system) as .py code, which is correct.
- `unsloth` and `deepspeed`: have real credential/execution patterns outside code fences.

<!-- calibration_history: [{"date":"2026-04-08","scorer_v":"0.2.0","matrix_v":"0.1.1"}] -->
